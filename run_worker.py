"""Standalone CV worker. Run the FastAPI service in a separate process."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import os
from pathlib import Path
import threading

from dotenv import load_dotenv
from app.storage.local import LocalStorageProvider
from engine.config import ROOT, build_rules, inference_options, load_config
from engine.deduplication.anti_spam import AntiSpamEngine
from engine.incident_client import IncidentClient
from engine.inference.factory import create_inference_engine
from engine.pipeline import CVPipeline
from engine.sources.factory import create_video_source
from engine.tracking.tracker import ByteTracker

log = logging.getLogger("linq.worker")


def run_camera_worker(camera, config, options, stop_event, sink, max_frames=None, realtime=True, loop=False):
    source = None
    engine = None
    frames = None
    try:
        engine = create_inference_engine(**options)
        rules = build_rules(config, camera, engine.class_names)
        source = create_video_source(camera["source"], realtime=realtime, loop=loop)
        source.stop_event = stop_event
        tracking = dict(config.get("tracking", {}))
        algorithm = tracking.pop("algorithm", "bytetrack")
        if algorithm != "bytetrack":
            raise ValueError(f"Unknown tracker: {algorithm}")
        for long_name, short_name in [
            ("high_threshold", "high_thresh"),
            ("low_threshold", "low_thresh"),
            ("match_threshold_high", "match_thresh_high"),
            ("match_threshold_low", "match_thresh_low"),
        ]:
            if long_name in tracking:
                tracking[short_name] = tracking.pop(long_name)
        anti_spam = dict(config.get("deduplication", {}))
        for env_key, option, cast in [
            ("DEBOUNCE_FRAMES", "debounce_frames", int),
            ("COOLDOWN_SECONDS", "cooldown_seconds", float),
        ]:
            if env_key in os.environ:
                anti_spam[option] = cast(os.environ[env_key])
        pipeline = CVPipeline(
            inference_engine=engine,
            tracker=ByteTracker(**tracking),
            rules_engine=rules,
            anti_spam_engine=AntiSpamEngine(**anti_spam),
            storage_provider=LocalStorageProvider(str(ROOT / "storage" / "snapshots")),
            incident_callback=lambda event, image: sink.submit(event, image, camera),
            camera_id=camera["camera_id"],
        )
        log.info("%s: backend=%s source=%s", camera["camera_id"], options["backend"], camera["source"])
        frames = iter(source)
        count = 0
        sequence_id = getattr(source, "sequence_id", 0)
        for frame, timestamp in frames:
            if stop_event.is_set():
                break
            next_sequence = getattr(source, "sequence_id", 0)
            if next_sequence != sequence_id:
                pipeline.reset()
                sequence_id = next_sequence
            result = pipeline.process_frame(frame, timestamp=timestamp, source_fps=source.fps)
            count += 1
            if result.new_incidents:
                log.info("%s: %d confirmed incidents queued", camera["camera_id"], len(result.new_incidents))
            if max_frames and count >= max_frames:
                break
        if count == 0 and not stop_event.is_set():
            raise RuntimeError(f"No frames decoded for {camera['camera_id']}")
        return count
    except Exception:
        stop_event.set()
        raise
    finally:
        if source:
            source.stop()
        if frames and hasattr(frames, "close"):
            frames.close()
        if engine:
            engine.close()


def main(argv=None):
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="CV worker: real inference or explicit MOCK demo")
    parser.add_argument("--config", default=str(ROOT / "configs" / "cv_engine.yaml"))
    parser.add_argument("--source", action="append", help="Video/RTSP/image directory; repeat for each configured camera")
    parser.add_argument("--backend", choices=["linq_tpu", "onnx_cpu", "mock", "linq", "onnx"])
    parser.add_argument("--model")
    parser.add_argument("--api-url", default=os.getenv("CV_API_URL", "http://127.0.0.1:8000/api/v1"))
    parser.add_argument("--no-api", action="store_true", help="Offline mode: retain events and JPEGs in outbox")
    parser.add_argument("--outbox", default=str(ROOT / "data" / "cv_outbox"))
    parser.add_argument("--max-frames", type=int)
    parser.add_argument("--fast", action="store_true", help="Process files without playback pacing")
    parser.add_argument("--loop", action="store_true", help="Explicitly loop file sources")
    args = parser.parse_args(argv)
    if args.max_frames is not None and args.max_frames <= 0:
        parser.error("--max-frames must be positive")
    config = load_config(args.config)
    options = inference_options(config, args.backend, args.model)
    cameras = [dict(row) for row in config.get("cameras", [])]
    if not cameras:
        parser.error("Configure cameras with camera_id and site_id in YAML")
    if args.source:
        if len(args.source) > len(cameras):
            parser.error("Each --source needs a corresponding camera entry in YAML")
        cameras = cameras[: len(args.source)]
        for camera, source in zip(cameras, args.source):
            camera["source"] = source
    seen = set()
    for camera in cameras:
        if not camera.get("camera_id") or not camera.get("site_id"):
            parser.error("Each camera needs camera_id and site_id matching the backend")
        if camera["camera_id"] in seen:
            parser.error("camera_id must be unique")
        seen.add(camera["camera_id"])
        if not camera.get("source"):
            if options["backend"] == "MOCK":
                camera["source"] = "synthetic"
            else:
                parser.error("Provide a real --source or camera.source in YAML")
        spec = camera["source"]
        if not spec.startswith(("synthetic", "rtsp://", "rtsps://", "http://", "https://")) and not Path(spec).is_absolute():
            camera["source"] = str(ROOT / spec)
    if options["backend"] == "LINQ_TPU" and len(cameras) > 1:
        parser.error("Use one TPU stream until concurrent device execution is verified on the stand")
    sink = IncidentClient(None if args.no_api else args.api_url, args.outbox)
    stop = threading.Event()
    pool = ThreadPoolExecutor(max_workers=len(cameras))
    sink.start()
    exit_code = 0
    try:
        futures = [
            pool.submit(
                run_camera_worker,
                camera,
                config,
                options,
                stop,
                sink,
                args.max_frames,
                not args.fast,
                args.loop,
            )
            for camera in cameras
        ]
        for future in as_completed(futures):
            log.info("Stream finished: %d frames", future.result())
    except KeyboardInterrupt:
        stop.set()
    except Exception:
        log.exception("CV worker failed")
        stop.set()
        exit_code = 1
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
        sink.close()
    return exit_code


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    raise SystemExit(main())
