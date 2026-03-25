# orders/throttles.py
from rest_framework.throttling import UserRateThrottle


class ReorderThrottle(UserRateThrottle):
    scope = "reorder"