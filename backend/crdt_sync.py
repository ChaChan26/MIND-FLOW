"""
CRDT Multi-Device State Sync Engine for MIND-FLOW Phase 3.

Provides Conflict-Free Replicated Data Types (CvRDTs) and Hybrid Logical Clocks (HLC)
for deterministic multi-device state convergence without centralized locks.

Primitives:
- HLCTimestamp: Monotonic triple (physical_time, logical_counter, node_id)
- HybridLogicalClock (HLC): Generator and updater for HLC timestamps
- PNCounter: Positive-Negative Counter CvRDT
- LWWElementSet: Last-Write-Wins Element Set CvRDT (presence bias for ties)
- LWWRegister: Last-Write-Wins Register CvRDT
- CRDTSyncEngine: High-level engine encapsulating battery state, category rules,
  discrete counters, and session logs.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
"""

import time
import uuid
import json
import threading
from typing import Any, Dict, List, Optional, Set, Tuple, Union


class HLCTimestamp:
    """
    Hybrid Logical Clock timestamp tuple (physical_time, logical_counter, node_id).
    Provides total ordering:
    (physical_time, logical_counter, node_id)
    """

    def __init__(self, physical_time: float, logical_counter: int, node_id: str):
        self.physical_time = float(physical_time)
        self.logical_counter = int(logical_counter)
        self.node_id = str(node_id)

    def to_tuple(self) -> Tuple[float, int, str]:
        return (self.physical_time, self.logical_counter, self.node_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "physical_time": self.physical_time,
            "logical_counter": self.logical_counter,
            "node_id": self.node_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HLCTimestamp':
        return cls(
            physical_time=data["physical_time"],
            logical_counter=data["logical_counter"],
            node_id=data["node_id"]
        )

    @classmethod
    def from_value(cls, val: Any, default_node_id: str = "") -> 'HLCTimestamp':
        if isinstance(val, HLCTimestamp):
            return val
        elif isinstance(val, dict):
            return cls.from_dict(val)
        elif isinstance(val, (tuple, list)):
            pt = val[0]
            lc = val[1] if len(val) > 1 else 0
            nid = val[2] if len(val) > 2 else default_node_id
            return cls(pt, lc, nid)
        elif isinstance(val, (int, float)):
            return cls(float(val), 0, default_node_id)
        else:
            raise ValueError(f"Cannot convert {type(val)} ({val}) to HLCTimestamp")

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, HLCTimestamp):
            other = HLCTimestamp.from_value(other)
        return self.to_tuple() < other.to_tuple()

    def __le__(self, other: Any) -> bool:
        if not isinstance(other, HLCTimestamp):
            other = HLCTimestamp.from_value(other)
        return self.to_tuple() <= other.to_tuple()

    def __gt__(self, other: Any) -> bool:
        if not isinstance(other, HLCTimestamp):
            other = HLCTimestamp.from_value(other)
        return self.to_tuple() > other.to_tuple()

    def __ge__(self, other: Any) -> bool:
        if not isinstance(other, HLCTimestamp):
            other = HLCTimestamp.from_value(other)
        return self.to_tuple() >= other.to_tuple()

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, HLCTimestamp):
            try:
                other = HLCTimestamp.from_value(other)
            except Exception:
                return False
        return self.to_tuple() == other.to_tuple()

    def __ne__(self, other: Any) -> bool:
        return not (self == other)

    def __hash__(self) -> int:
        return hash(self.to_tuple())

    def __repr__(self) -> str:
        return f"HLCTimestamp({self.physical_time:.4f}, {self.logical_counter}, '{self.node_id}')"


class HybridLogicalClock:
    """
    Hybrid Logical Clock implementation combining physical time with a logical counter.
    Thread-safe and monotonic.
    """

    def __init__(self, node_id: Optional[str] = None):
        self.node_id = str(node_id) if node_id else str(uuid.uuid4())
        self.l = 0.0
        self.c = 0
        self._lock = threading.Lock()

    def send(self) -> HLCTimestamp:
        return self.now()

    def get_timestamp(self) -> HLCTimestamp:
        return self.now()

    def now(self) -> HLCTimestamp:
        with self._lock:
            pt = time.time()
            l_new = max(self.l, pt)
            if l_new == self.l:
                self.c += 1
            else:
                self.l = l_new
                self.c = 0
            return HLCTimestamp(self.l, self.c, self.node_id)

    MAX_DRIFT = 300.0  # Maximum acceptable physical clock skew in seconds (5 minutes)

    def update(self, remote_ts: Any) -> HLCTimestamp:
        remote = HLCTimestamp.from_value(remote_ts, default_node_id=self.node_id)
        with self._lock:
            pt = time.time()
            l_remote = remote.physical_time
            if l_remote > pt + self.MAX_DRIFT:
                l_remote = pt + self.MAX_DRIFT
            c_remote = remote.logical_counter

            l_new = max(self.l, l_remote, pt)
            if l_new == self.l and l_new == l_remote:
                self.c = max(self.c, c_remote) + 1
            elif l_new == self.l:
                self.c += 1
            elif l_new == l_remote:
                self.c = c_remote + 1
            else:
                self.c = 0
            self.l = l_new
            return HLCTimestamp(self.l, self.c, self.node_id)

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "node_id": self.node_id,
                "l": self.l,
                "c": self.c
            }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HybridLogicalClock':
        clock = cls(node_id=data["node_id"])
        clock.l = float(data.get("l", 0.0))
        clock.c = int(data.get("c", 0))
        return clock


class PNCounter:
    """
    Positive-Negative Counter CvRDT.
    State consists of two vectors P and N mapping node_id -> counter value.
    Thread-safe implementation with internal RLock.
    """

    def __init__(self, P: Optional[Dict[str, int]] = None, N: Optional[Dict[str, int]] = None):
        self._lock = threading.RLock()
        self.P: Dict[str, int] = {str(k): int(v) for k, v in P.items()} if P else {}
        self.N: Dict[str, int] = {str(k): int(v) for k, v in N.items()} if N else {}

    def increment(self, node_id: str, val: int = 1) -> None:
        if val < 0:
            raise ValueError("Increment value must be non-negative")
        nid = str(node_id)
        with self._lock:
            self.P[nid] = self.P.get(nid, 0) + int(val)

    def decrement(self, node_id: str, val: int = 1) -> None:
        if val < 0:
            raise ValueError("Decrement value must be non-negative")
        nid = str(node_id)
        with self._lock:
            self.N[nid] = self.N.get(nid, 0) + int(val)

    @property
    def value(self) -> int:
        with self._lock:
            return sum(self.P.values()) - sum(self.N.values())

    def merge(self, other: 'PNCounter') -> 'PNCounter':
        if self is other:
            return self
        first, second = (self, other) if id(self) < id(other) else (other, self)
        with first._lock:
            with second._lock:
                other_p = dict(other.P)
                other_n = dict(other.N)

                new_P: Dict[str, int] = {}
                all_p_nodes = set(self.P.keys()).union(set(other_p.keys()))
                for n in all_p_nodes:
                    new_P[n] = max(self.P.get(n, 0), other_p.get(n, 0))

                new_N: Dict[str, int] = {}
                all_n_nodes = set(self.N.keys()).union(set(other_n.keys()))
                for n in all_n_nodes:
                    new_N[n] = max(self.N.get(n, 0), other_n.get(n, 0))

                return PNCounter(P=new_P, N=new_N)

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "type": "PNCounter",
                "P": dict(self.P),
                "N": dict(self.N)
            }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PNCounter':
        return cls(P=data.get("P", {}), N=data.get("N", {}))

    def __repr__(self) -> str:
        return f"PNCounter(value={self.value})"


class LWWRegister:
    """
    Last-Write-Wins Register CvRDT.
    Stores value along with HLCTimestamp and node_id.
    Thread-safe implementation with internal RLock.
    """

    def __init__(self, value: Any = None, timestamp: Any = None, node_id: str = ""):
        self._lock = threading.RLock()
        self._value = value
        self.node_id = str(node_id)
        if timestamp is None:
            self.timestamp = HLCTimestamp(0.0, 0, self.node_id)
        else:
            self.timestamp = HLCTimestamp.from_value(timestamp, default_node_id=self.node_id)

    @property
    def value(self) -> Any:
        with self._lock:
            return self._value

    def set(self, value: Any, timestamp: Any = None, node_id: str = "") -> None:
        nid = node_id if node_id else self.node_id
        if timestamp is None:
            ts = HLCTimestamp(time.time(), 0, nid)
        else:
            ts = HLCTimestamp.from_value(timestamp, default_node_id=nid)

        with self._lock:
            if ts > self.timestamp:
                self._value = value
                self.timestamp = ts
                self.node_id = nid
            elif ts == self.timestamp:
                # Deterministic tie breaking
                if nid >= self.node_id:
                    self._value = value
                    self.timestamp = ts
                    self.node_id = nid

    def merge(self, other: 'LWWRegister') -> 'LWWRegister':
        if self is other:
            return self
        first, second = (self, other) if id(self) < id(other) else (other, self)
        with first._lock:
            with second._lock:
                if other.timestamp > self.timestamp:
                    return LWWRegister(value=other._value, timestamp=other.timestamp, node_id=other.node_id)
                elif self.timestamp > other.timestamp:
                    return LWWRegister(value=self._value, timestamp=self.timestamp, node_id=self.node_id)
                else:
                    # Equal timestamps: tie break by node_id
                    if other.node_id >= self.node_id:
                        return LWWRegister(value=other._value, timestamp=other.timestamp, node_id=other.node_id)
                    else:
                        return LWWRegister(value=self._value, timestamp=self.timestamp, node_id=self.node_id)

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "type": "LWWRegister",
                "value": self._value,
                "timestamp": self.timestamp.to_dict(),
                "node_id": self.node_id
            }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LWWRegister':
        ts = HLCTimestamp.from_dict(data["timestamp"]) if "timestamp" in data and isinstance(data["timestamp"], dict) else data.get("timestamp")
        return cls(value=data.get("value"), timestamp=ts, node_id=data.get("node_id", ""))

    def __repr__(self) -> str:
        return f"LWWRegister(value={self.value}, timestamp={self.timestamp})"


class LWWElementSet:
    """
    Last-Write-Wins Element Set CvRDT.
    Maintains add_set and remove_set with timestamps.
    Conflict resolution: LWW bias for presence (add_ts >= remove_ts => present).
    Thread-safe implementation with internal RLock.
    """

    def __init__(self, add_set: Optional[Dict[str, Any]] = None,
                 remove_set: Optional[Dict[str, Any]] = None,
                 elements: Optional[Dict[str, Any]] = None):
        self._lock = threading.RLock()
        self.add_set: Dict[str, HLCTimestamp] = {
            k: HLCTimestamp.from_value(v) for k, v in add_set.items()
        } if add_set else {}
        self.remove_set: Dict[str, HLCTimestamp] = {
            k: HLCTimestamp.from_value(v) for k, v in remove_set.items()
        } if remove_set else {}
        self.elements: Dict[str, Any] = dict(elements) if elements else {}

    def _element_key(self, element: Any) -> str:
        if isinstance(element, str):
            return element
        elif isinstance(element, (dict, list, tuple)):
            try:
                return json.dumps(element, sort_keys=True)
            except Exception:
                return str(element)
        else:
            return str(element)

    def add(self, element: Any, timestamp: Any = None, node_id: str = "") -> None:
        key = self._element_key(element)
        if timestamp is not None:
            ts = HLCTimestamp.from_value(timestamp, default_node_id=node_id)
        else:
            ts = HLCTimestamp(time.time(), 0, node_id)

        with self._lock:
            if key not in self.add_set or ts > self.add_set[key]:
                self.add_set[key] = ts
                self.elements[key] = element

    def remove(self, element: Any, timestamp: Any = None, node_id: str = "") -> None:
        key = self._element_key(element)
        if timestamp is not None:
            ts = HLCTimestamp.from_value(timestamp, default_node_id=node_id)
        else:
            ts = HLCTimestamp(time.time(), 0, node_id)

        with self._lock:
            if key not in self.remove_set or ts > self.remove_set[key]:
                self.remove_set[key] = ts
                if key not in self.elements:
                    self.elements[key] = element

    def read(self) -> Set[Any]:
        with self._lock:
            result = set()
            for key, element in self.elements.items():
                if key in self.add_set:
                    add_ts = self.add_set[key]
                    remove_ts = self.remove_set.get(key)
                    if remove_ts is None or add_ts >= remove_ts:
                        if isinstance(element, (dict, list)):
                            try:
                                if isinstance(element, dict):
                                    result.add(json.dumps(element, sort_keys=True))
                                else:
                                    result.add(tuple(element))
                            except Exception:
                                result.add(str(element))
                        else:
                            result.add(element)
            return result

    def read_elements(self) -> List[Any]:
        """Return list of active element payloads."""
        with self._lock:
            result = []
            for key, element in self.elements.items():
                if key in self.add_set:
                    add_ts = self.add_set[key]
                    remove_ts = self.remove_set.get(key)
                    if remove_ts is None or add_ts >= remove_ts:
                        result.append(element)
            return result

    def merge(self, other: 'LWWElementSet') -> 'LWWElementSet':
        if self is other:
            return self
        first, second = (self, other) if id(self) < id(other) else (other, self)
        with first._lock:
            with second._lock:
                other_add_set = dict(other.add_set)
                other_remove_set = dict(other.remove_set)
                other_elements = dict(other.elements)

            new_add_set: Dict[str, HLCTimestamp] = {}
            new_remove_set: Dict[str, HLCTimestamp] = {}
            new_elements: Dict[str, Any] = {}

            all_add_keys = set(self.add_set.keys()).union(set(other_add_set.keys()))
            for k in all_add_keys:
                ts1 = self.add_set.get(k)
                ts2 = other_add_set.get(k)
                if ts1 and ts2:
                    new_add_set[k] = max(ts1, ts2)
                elif ts1:
                    new_add_set[k] = ts1
                else:
                    new_add_set[k] = ts2

            all_remove_keys = set(self.remove_set.keys()).union(set(other_remove_set.keys()))
            for k in all_remove_keys:
                ts1 = self.remove_set.get(k)
                ts2 = other_remove_set.get(k)
                if ts1 and ts2:
                    new_remove_set[k] = max(ts1, ts2)
                elif ts1:
                    new_remove_set[k] = ts1
                else:
                    new_remove_set[k] = ts2

            all_element_keys = set(self.elements.keys()).union(set(other_elements.keys()))
            for k in all_element_keys:
                e1 = self.elements.get(k)
                e2 = other_elements.get(k)
                ts1 = self.add_set.get(k)
                ts2 = other_add_set.get(k)
                if e1 is not None and e2 is not None and ts1 and ts2:
                    new_elements[k] = e1 if ts1 >= ts2 else e2
                elif e1 is not None:
                    new_elements[k] = e1
                else:
                    new_elements[k] = e2

            return LWWElementSet(add_set=new_add_set, remove_set=new_remove_set, elements=new_elements)

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "type": "LWWElementSet",
                "add_set": {k: ts.to_dict() for k, ts in self.add_set.items()},
                "remove_set": {k: ts.to_dict() for k, ts in self.remove_set.items()},
                "elements": dict(self.elements)
            }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LWWElementSet':
        add_set = {k: HLCTimestamp.from_dict(v) for k, v in data.get("add_set", {}).items()}
        remove_set = {k: HLCTimestamp.from_dict(v) for k, v in data.get("remove_set", {}).items()}
        elements = data.get("elements", {})
        return cls(add_set=add_set, remove_set=remove_set, elements=elements)

    def garbage_collect_tombstones(self, max_age_seconds: float = 86400.0) -> int:
        """Purge remove_set tombstone records older than max_age_seconds where element is no longer active."""
        now = time.time()
        purged = 0
        with self._lock:
            keys_to_purge = []
            for key, remove_ts in list(self.remove_set.items()):
                add_ts = self.add_set.get(key)
                is_removed = (add_ts is None or remove_ts > add_ts)
                if is_removed and (now - remove_ts.physical_time > max_age_seconds):
                    keys_to_purge.append(key)
            for key in keys_to_purge:
                self.remove_set.pop(key, None)
                self.add_set.pop(key, None)
                self.elements.pop(key, None)
                purged += 1
            return purged



class CRDTSyncEngine:
    """
    High-Level CRDT Synchronization Engine.
    Encapsulates stamina battery, category rules, scalar counters, and session logs.
    Thread-safe implementation with internal RLock.
    """

    def __init__(self, node_id: Optional[str] = None):
        self._lock = threading.RLock()
        self.hlc = HybridLogicalClock(node_id=node_id)
        self.node_id = self.hlc.node_id

        self.stamina_battery = LWWRegister(value=100.0, timestamp=self.hlc.now(), node_id=self.node_id)
        self.fatigue_score = LWWRegister(value=0.0, timestamp=self.hlc.now(), node_id=self.node_id)
        self.category_rules = LWWElementSet()
        self.counters: Dict[str, PNCounter] = {}
        self.session_logs = LWWElementSet()

    def update_stamina_battery(self, val: float, timestamp: Any = None) -> None:
        with self._lock:
            if timestamp is not None:
                self.hlc.update(timestamp)
                ts = timestamp
            else:
                ts = self.hlc.now()
            ts_obj = HLCTimestamp.from_value(ts, default_node_id=self.node_id)
            self.stamina_battery.set(val, timestamp=ts_obj, node_id=ts_obj.node_id)

    def get_stamina_battery(self) -> float:
        with self._lock:
            return float(self.stamina_battery.value)

    def update_fatigue_score(self, val: float, timestamp: Any = None) -> None:
        with self._lock:
            if timestamp is not None:
                self.hlc.update(timestamp)
                ts = timestamp
            else:
                ts = self.hlc.now()
            ts_obj = HLCTimestamp.from_value(ts, default_node_id=self.node_id)
            self.fatigue_score.set(val, timestamp=ts_obj, node_id=ts_obj.node_id)

    def get_fatigue_score(self) -> float:
        with self._lock:
            return float(self.fatigue_score.value)

    def update_battery_state(self, val: float, timestamp: Any = None) -> None:
        self.update_stamina_battery(val, timestamp=timestamp)

    def add_category_rule(self, rule: Any, timestamp: Any = None) -> None:
        with self._lock:
            if timestamp is not None:
                self.hlc.update(timestamp)
                ts = timestamp
            else:
                ts = self.hlc.now()
            ts_obj = HLCTimestamp.from_value(ts, default_node_id=self.node_id)
            self.category_rules.add(rule, timestamp=ts_obj, node_id=ts_obj.node_id)

    def set_category_rule(self, rule: Any, timestamp: Any = None) -> None:
        self.add_category_rule(rule, timestamp=timestamp)

    def remove_category_rule(self, rule: Any, timestamp: Any = None) -> None:
        with self._lock:
            if timestamp is not None:
                self.hlc.update(timestamp)
                ts = timestamp
            else:
                ts = self.hlc.now()
            ts_obj = HLCTimestamp.from_value(ts, default_node_id=self.node_id)
            self.category_rules.remove(rule, timestamp=ts_obj, node_id=ts_obj.node_id)

    def get_category_rules(self) -> List[Any]:
        with self._lock:
            return self.category_rules.read_elements()

    def increment_counter(self, name: str, val: int = 1) -> None:
        with self._lock:
            if name not in self.counters:
                self.counters[name] = PNCounter()
            self.counters[name].increment(self.node_id, val)

    def decrement_counter(self, name: str, val: int = 1) -> None:
        with self._lock:
            if name not in self.counters:
                self.counters[name] = PNCounter()
            self.counters[name].decrement(self.node_id, val)

    def get_counter_value(self, name: str) -> int:
        with self._lock:
            if name not in self.counters:
                return 0
            return self.counters[name].value

    def add_session_log(self, session_uuid: str, log_data: dict, timestamp: Any = None) -> None:
        with self._lock:
            ts = self.hlc.update(timestamp) if timestamp else self.hlc.now()
            entry = {"session_uuid": session_uuid, "log_data": log_data, "node_id": self.node_id}
            self.session_logs.add(entry, timestamp=ts, node_id=self.node_id)

    def get_session_logs(self) -> List[dict]:
        with self._lock:
            return self.session_logs.read_elements()

    def export_state(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "node_id": self.node_id,
                "hlc": self.hlc.to_dict(),
                "stamina_battery": self.stamina_battery.to_dict(),
                "fatigue_score": self.fatigue_score.to_dict(),
                "category_rules": self.category_rules.to_dict(),
                "counters": {k: v.to_dict() for k, v in self.counters.items()},
                "session_logs": self.session_logs.to_dict()
            }

    def to_dict(self) -> Dict[str, Any]:
        return self.export_state()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CRDTSyncEngine':
        node_id = data.get("node_id", str(uuid.uuid4()))
        engine = cls(node_id=node_id)
        if "hlc" in data:
            engine.hlc = HybridLogicalClock.from_dict(data["hlc"])
        if "stamina_battery" in data:
            engine.stamina_battery = LWWRegister.from_dict(data["stamina_battery"])
        if "fatigue_score" in data:
            engine.fatigue_score = LWWRegister.from_dict(data["fatigue_score"])
        if "category_rules" in data:
            engine.category_rules = LWWElementSet.from_dict(data["category_rules"])
        if "counters" in data:
            engine.counters = {k: PNCounter.from_dict(v) for k, v in data["counters"].items()}
        if "session_logs" in data:
            engine.session_logs = LWWElementSet.from_dict(data["session_logs"])
        return engine

    def merge_state(self, remote: Union[Dict[str, Any], 'CRDTSyncEngine']) -> 'CRDTSyncEngine':
        if isinstance(remote, dict):
            remote_engine = CRDTSyncEngine.from_dict(remote)
        else:
            remote_engine = remote

        if self is remote_engine:
            return self

        first, second = (self, remote_engine) if id(self) < id(remote_engine) else (remote_engine, self)
        with first._lock:
            with second._lock:
                # Update HLC clock with remote clock state
                self.hlc.update(remote_engine.hlc.now())

                # Merge registers
                self.stamina_battery = self.stamina_battery.merge(remote_engine.stamina_battery)
                self.fatigue_score = self.fatigue_score.merge(remote_engine.fatigue_score)

                # Merge category rules
                self.category_rules = self.category_rules.merge(remote_engine.category_rules)

                # Merge counters
                all_counters = set(self.counters.keys()).union(set(remote_engine.counters.keys()))
                for c in all_counters:
                    c1 = self.counters.get(c, PNCounter())
                    c2 = remote_engine.counters.get(c, PNCounter())
                    self.counters[c] = c1.merge(c2)

                # Merge session logs
                self.session_logs = self.session_logs.merge(remote_engine.session_logs)

            return self

    def garbage_collect_tombstones(self, max_age_seconds: float = 86400.0) -> int:
        """Purge expired tombstones from category_rules and session_logs."""
        with self._lock:
            c1 = self.category_rules.garbage_collect_tombstones(max_age_seconds)
            c2 = self.session_logs.garbage_collect_tombstones(max_age_seconds)
            return c1 + c2

    def export_delta(self, since_physical_time: Optional[float] = None) -> Dict[str, Any]:
        """Export state changes created after since_physical_time."""
        with self._lock:
            state = self.export_state()
            if since_physical_time is None:
                return state

            filtered_cat_add = {k: v for k, v in state["category_rules"]["add_set"].items() if v["physical_time"] > since_physical_time}
            filtered_cat_rem = {k: v for k, v in state["category_rules"]["remove_set"].items() if v["physical_time"] > since_physical_time}
            state["category_rules"]["add_set"] = filtered_cat_add
            state["category_rules"]["remove_set"] = filtered_cat_rem

            filtered_logs_add = {k: v for k, v in state["session_logs"]["add_set"].items() if v["physical_time"] > since_physical_time}
            filtered_logs_rem = {k: v for k, v in state["session_logs"]["remove_set"].items() if v["physical_time"] > since_physical_time}
            state["session_logs"]["add_set"] = filtered_logs_add
            state["session_logs"]["remove_set"] = filtered_logs_rem

            return state

