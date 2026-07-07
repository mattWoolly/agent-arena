import time
from collections import OrderedDict


class LRUCache:
    """A least-recently-used cache with optional per-entry TTL.

    - `capacity`: max number of entries; inserting beyond it evicts the
      least recently used entry. Both `get` and `put` count as "use".
    - `ttl`: seconds an entry stays valid, or None for no expiry.
      Expired entries behave as absent and are removed when noticed.
    - `clock`: injectable time source (for tests).
    """

    def __init__(self, capacity, ttl=None, clock=time.monotonic):
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self.capacity = capacity
        self.ttl = ttl
        self._clock = clock
        self._data = OrderedDict()  # key -> (value, inserted_at)

    def get(self, key, default=None):
        if key not in self._data:
            return default
        value, ts = self._data[key]
        if self.ttl is not None and self._clock() - ts > self.ttl:
            del self._data[key]
            return default
        return value

    def put(self, key, value):
        if len(self._data) >= self.capacity:
            self._data.popitem(last=False)
        self._data[key] = (value, self._clock())
        self._data.move_to_end(key)

    def __len__(self):
        return len(self._data)

    def __contains__(self, key):
        return self.get(key, default=_MISSING) is not _MISSING


_MISSING = object()
