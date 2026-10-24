"""Regressions for incident continuity and real video time, independent of inference speed."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from engine.deduplication.anti_spam import AntiSpamEngine
from engine.deduplication.types import IncidentState
from engine.inference.base import BoundingBox, Detection
from engine.inference.mock import MockInferenceEngine
from engine.pipeline import CVPipeline
from engine.rules.base import FrameContext, RuleViolation, ViolationSeverity
from engine.rules.engine import RulesEngine
from engine.rules.fall_detection import FallDetectionRule
from engine.rules.ppe_compliance import PPEComplianceRule
from engine.sources.synthetic import SyntheticSource
from engine.sources.video import RtspSource, VideoFileSource
from engine.tracking.tracker import ByteTracker
from engine.tracking.types import TrackedObject, TrackState


def detection(x=100, class_id=0, name="person", confidence=0.9):
    return Detection(BoundingBox(x, 100, x + 100, 300), confidence, class_id, name)


def violation(rule_id="helmet", camera="cam"):
    return RuleViolation("ppe_compliance", rule_id, ViolationSeverity.HIGH, 0, camera, 1)


def context(frame, timestamp=None, camera="cam", fps=25):
    return FrameContext(frame, frame / 25 if timestamp is None else timestamp,
                        camera_id=camera, fps=fps)


def test_lost_identity_survives_occlusion_but_predictions_are_not_observations():
    tracker = ByteTracker(min_hits_to_confirm=1, max_lost_frames=4)
    original = tracker.update([detection()])[0].track_id
    assert tracker.update([]) == []
    assert tracker.update([]) == []
    recovered = tracker.update([detection()])
    assert [track.track_id for track in recovered] == [original]
    assert recovered[0].time_since_update == 0
    for _ in range(5):
        assert tracker.update([]) == []
    assert tracker.update([detection()])[0].track_id != original


def test_confirmation_respects_configured_hits():
    tracker = ByteTracker(min_hits_to_confirm=4)
    for _ in range(3):
        assert tracker.update([detection()]) == []
    assert len(tracker.update([detection()])) == 1


def test_iou_distance_threshold_allows_moderate_motion_without_changing_class():
    tracker = ByteTracker(min_hits_to_confirm=1, match_thresh_high=0.75)
    original = tracker.update([detection()])[0].track_id
    # IoU 0.43, distance 0.57: valid below a max-distance threshold of 0.75.
    assert tracker.update([detection(x=140)])[0].track_id == original
    # An overlapping vehicle must never inherit the person's track ID.
    vehicle = tracker.update([detection(x=150, class_id=1, name="forklift")])[0]
    assert vehicle.track_id != original


def test_ppe_types_have_independent_streaks_and_duplicate_rows_do_not_accelerate():
    spam = AntiSpamEngine(debounce_frames=3)
    helmet, vest = violation("helmet"), violation("vest")
    for frame in (1, 2):
        new, _ = spam.process([helmet, helmet, vest], context(frame))
        assert new == []
    new, _ = spam.process([helmet, vest], context(3))
    assert {incident.rule_id for incident in new} == {"helmet", "vest"}


def test_debounce_requires_consecutive_frames_and_elapsed_media_time():
    spam = AntiSpamEngine(debounce_frames=2, debounce_seconds=1.5)
    v = violation()
    assert spam.process([v], context(1, 0))[0] == []
    assert spam.process([v], context(2, 1))[0] == []
    spam.process([], context(3, 1.4))
    assert spam.process([v], context(4, 1.5))[0] == []
    assert spam.process([v], context(5, 2.9))[0] == []
    assert len(spam.process([v], context(6, 3.0))[0]) == 1


def test_continuing_incident_never_expires_at_cooldown_boundary():
    spam = AntiSpamEngine(debounce_frames=1, cooldown_seconds=2, resolve_frames=2)
    v = violation()
    new, _ = spam.process([v], context(1, 0))
    incident_id = new[0].incident_id
    for frame in range(2, 20):
        new, active = spam.process([v], context(frame, frame))
        assert new == []
        assert [inc.incident_id for inc in active] == [incident_id]
    spam.process([], context(20, 20, fps=100000))
    assert spam.process([], context(21, 21, fps=0))[1] == []
    new, _ = spam.process([v], context(22, 22))
    assert new[0].incident_id != incident_id


def test_resolution_is_frame_based_and_reactivation_clears_resolved_at():
    spam = AntiSpamEngine(debounce_frames=1, cooldown_seconds=60, resolve_frames=2)
    v = violation()
    incident = spam.process([v], context(1, 0))[0][0]
    assert len(spam.process([], context(2, 100, fps=100000))[1]) == 1
    assert spam.process([], context(3, 101, fps=100000))[1] == []
    assert incident.state == IncidentState.RESOLVED
    # A separate sequence verifies reactivation inside the cooldown.
    spam.reset()
    incident = spam.process([v], context(1, 0))[0][0]
    spam.process([], context(2, 1))
    spam.process([], context(3, 2))
    new, active = spam.process([v], context(4, 3))
    assert new == []
    assert active[0] is incident and incident.resolved_at is None


def test_other_cameras_do_not_interrupt_debounce():
    spam = AntiSpamEngine(debounce_frames=2)
    spam.process([violation()], context(1))
    spam.process([], context(1, camera="other"))
    assert len(spam.process([violation()], context(2))[0]) == 1


def test_fall_requires_three_seconds_and_lost_prediction_resets_streak():
    rule = FallDetectionRule(min_frames_lying=2)
    fallen = TrackedObject(1, 0, "person", BoundingBox(0, 0, 160, 60), .9)
    for frame in range(30):
        assert rule.evaluate([fallen], context(frame, frame / 10)) == []
    assert len(rule.evaluate([fallen], context(30, 3))) == 1
    fallen.time_since_update = 1
    assert rule.evaluate([fallen], context(31, 3.1)) == []
    fallen.time_since_update = 0
    assert rule.evaluate([fallen], context(32, 3.2)) == []
    assert rule.evaluate([fallen], context(33, 6.1)) == []
    assert len(rule.evaluate([fallen], context(34, 6.2))) == 1


def test_rules_ignore_unobserved_track_for_ppe():
    rules = RulesEngine([PPEComplianceRule()])
    stale = TrackedObject(1, 0, "person", BoundingBox(0, 0, 100, 200), .9,
                          state=TrackState.LOST, time_since_update=1)
    ctx = context(1)
    ctx.all_detections = [detection(x=500)]
    assert rules.evaluate([stale], ctx) == []


def test_pipeline_reset_clears_temporal_rule_state():
    fall = FallDetectionRule(min_frames_lying=1, min_lying_seconds=3)
    pipeline = CVPipeline(inference_engine=MockInferenceEngine(),
                          rules_engine=RulesEngine([fall]), storage_provider=MagicMock())
    fallen = TrackedObject(1, 0, "person", BoundingBox(0, 0, 160, 60), .9)
    fall.evaluate([fallen], context(1, 0))
    pipeline.reset()
    assert fall.evaluate([fallen], context(2, 10)) == []


def test_synthetic_offline_timestamp_uses_source_time():
    with patch("engine.sources.synthetic.time.time", return_value=1000):
        samples = list(SyntheticSource(fps=2, realtime=False, max_frames=4))
    assert [ts for _, ts in samples] == [1000, 1000.5, 1001, 1001.5]


def test_video_close_releases_capture_and_timestamps_media(tmp_path):
    path = tmp_path / "sample.mp4"
    path.touch()
    frame = np.zeros((2, 2, 3), dtype=np.uint8)
    capture = MagicMock()
    capture.isOpened.return_value = True
    capture.get.return_value = 5
    capture.read.return_value = (True, frame)
    with patch("engine.sources.video.cv2.VideoCapture", return_value=capture), \
            patch("engine.sources.video.time.time", return_value=1000):
        source = VideoFileSource(str(path), realtime=False)
        capture.release.reset_mock()
        iterator = iter(source)
        assert next(iterator)[1] == 1000
        assert next(iterator)[1] == pytest.approx(1000.2)
        iterator.close()
        capture.release.assert_called_once()


def test_bad_looping_video_raises_instead_of_spinning(tmp_path):
    path = tmp_path / "bad.mp4"
    path.touch()
    capture = MagicMock()
    capture.isOpened.return_value = True
    capture.get.return_value = 25
    capture.read.return_value = (False, None)
    with patch("engine.sources.video.cv2.VideoCapture", return_value=capture):
        source = VideoFileSource(str(path), loop=True, realtime=False)
        with pytest.raises(RuntimeError, match="Cannot decode"):
            next(iter(source))
        assert capture.read.call_count == 2


def test_failed_rtsp_open_still_releases_capture():
    source = RtspSource("rtsp://example.invalid/test")
    capture = MagicMock()
    capture.isOpened.return_value = False
    with patch("engine.sources.video.cv2.VideoCapture", return_value=capture), \
            patch("engine.sources.video.time.sleep", side_effect=lambda _: source.stop()):
        assert list(source) == []
    capture.release.assert_called_once()
