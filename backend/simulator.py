# backend/simulator.py

import random
from typing import Dict


def generate_normal() -> Dict[str, float]:
    """Return a synthetic normal-traffic sample."""
    return {
        "duration": round(random.uniform(0.1, 1.0), 4),
        "protocol_type": random.choice(["tcp", "udp"]),
        "src_bytes": round(random.uniform(100, 1000), 2),
        "dst_bytes": round(random.uniform(100, 1000), 2),
    }


def generate_ddos() -> Dict[str, float]:
    """Return a synthetic DDoS-traffic sample."""
    return {
        "duration": round(random.uniform(0.0, 0.2), 4),
        "protocol_type": random.choice(["tcp", "udp", "icmp"]),
        "src_bytes": round(random.uniform(10000, 20000), 2),
        "dst_bytes": round(random.uniform(0, 10), 2),
    }
