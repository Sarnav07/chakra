# STUB created by P2 - owner P3 replaces this file
"""Pickup confirmation, compost arrival and batches (SPEC Section 11)."""


def confirm_pickup(conn, route_id, bin_id, level=None, staff_note=None) -> dict:
    raise NotImplementedError("STUB - owner P3 implements this")


def arrive_compost(conn, route_id) -> dict:
    raise NotImplementedError("STUB - owner P3 implements this")


def list_batches(conn, status="all") -> dict:
    raise NotImplementedError("STUB - owner P3 implements this")
