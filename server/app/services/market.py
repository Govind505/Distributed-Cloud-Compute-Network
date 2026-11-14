"""
Dynamic Spot Market & VCG Compute Auction Engine
Implements real-time dynamic pricing, market clearing rate calculations,
and second-price Vickrey auctions for opportunistic idle compute capacity.
"""
from datetime import datetime, timezone
import math


class SpotMarketService:
    """Calculates real-time spot rates based on fleet utilization and handles auction bids."""

    BASE_VCPU_RATE = 10.0
    BASE_GPU_RATE = 50.0

    def calculate_spot_rate(self, cluster_load_percent: float) -> dict:
        """Calculate dynamic spot pricing multiplier based on cluster load."""
        load = max(0.0, min(100.0, cluster_load_percent))
        
        # Quadratic dynamic elasticity curve:
        # Load 10% -> 0.51x base rate (49% discount)
        # Load 50% -> 0.87x base rate (13% discount)
        # Load 90% -> 1.71x base rate (surge pricing)
        multiplier = round(0.5 + 1.5 * ((load / 100.0) ** 2), 3)

        current_vcpu_spot = round(self.BASE_VCPU_RATE * multiplier, 2)
        current_gpu_spot = round(self.BASE_GPU_RATE * multiplier, 2)
        discount_percent = round((1.0 - multiplier) * 100.0, 1) if multiplier < 1.0 else 0.0

        market_condition = (
            "SURGE_PRICING" if multiplier > 1.3 else
            "STANDARD_MARKET" if multiplier >= 0.9 else
            "HIGH_DISCOUNT_OPPORTUNITY"
        )

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cluster_load_percent": round(load, 1),
            "spot_multiplier": multiplier,
            "market_condition": market_condition,
            "rates": {
                "vcpu_base_per_hour": self.BASE_VCPU_RATE,
                "vcpu_spot_per_hour": current_vcpu_spot,
                "gpu_base_per_hour": self.BASE_GPU_RATE,
                "gpu_spot_per_hour": current_gpu_spot,
            },
            "spot_discount_percent": discount_percent,
            "recommendation": (
                "Ideal time to submit spot batch workloads at maximum discount!"
                if discount_percent > 20 else
                "Moderate cluster demand. On-demand priority recommended for SLA-critical jobs."
            ),
        }

    def evaluate_spot_bid(self, max_bid: float, cores: float, gpus: int, cluster_load: float) -> dict:
        """Evaluate a client's spot bid using Vickrey 2nd-price clearing."""
        spot_info = self.calculate_spot_rate(cluster_load)
        clearing_hourly = (cores * spot_info["rates"]["vcpu_spot_per_hour"]) + (gpus * spot_info["rates"]["gpu_spot_per_hour"])
        
        accepted = max_bid >= clearing_hourly
        # In a Vickrey auction, winner pays the market clearing price (or second price)
        settled_rate = clearing_hourly if accepted else 0.0
        savings = round(max(0.0, max_bid - settled_rate), 2) if accepted else 0.0

        return {
            "bid_accepted": accepted,
            "client_max_bid": max_bid,
            "market_clearing_rate": clearing_hourly,
            "actual_charge_rate": settled_rate,
            "consumer_surplus_savings": savings,
            "auction_type": "Vickrey-Clarke-Groves (VCG) 2nd-Price Auction",
            "message": "Bid cleared successfully at market rate" if accepted else "Bid price below market clearing threshold",
        }


# Global singleton instance
spot_market_service = SpotMarketService()
