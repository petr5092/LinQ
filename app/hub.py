"""Раздача данных веб-клиентам: поток оповещений (SSE), кадры (MJPEG), показатели."""
import queue
import threading
import time


class Hub:
    def __init__(self):
        self.subs, self.lock = set(), threading.Lock()
        self.frames, self.cond = {}, threading.Condition()
        self.perf = {}
        self.camera_state, self.state_lock = {}, threading.Lock()

    def set_camera_state(self, cam, status, **details):
        now = time.time()
        with self.state_lock:
            state = self.camera_state.setdefault(cam, {"started_ts": now, "frames": 0})
            state.update(status=status, updated_ts=now, **details)

    def get_camera_states(self):
        with self.state_lock:
            return {cam: dict(state) for cam, state in self.camera_state.items()}

    def subscribe(self):
        q = queue.Queue(maxsize=200)
        with self.lock:
            self.subs.add(q)
        return q

    def unsubscribe(self, q):
        with self.lock:
            self.subs.discard(q)

    def publish(self, msg):
        with self.lock:
            subs = list(self.subs)
        for q in subs:
            try:
                q.put_nowait(msg)
            except queue.Full:
                pass

    def set_frame(self, cam, jpeg):
        with self.cond:
            seq = self.frames.get(cam, (0, b""))[0] + 1
            self.frames[cam] = (seq, jpeg)
            self.cond.notify_all()

    def wait_frame(self, cam, last_seq, timeout=5.0):
        with self.cond:
            self.cond.wait_for(lambda: self.frames.get(cam, (0,))[0] != last_seq, timeout)
            return self.frames.get(cam, (0, b""))
