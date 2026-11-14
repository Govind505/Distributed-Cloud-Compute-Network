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

    CLOUD_PRESETS = {
        "hetzner_dedicated": {
            "name": "Hetzner EX44 Dedicated (14 Core / 64GB RAM)",
            "monthly_cost_usd": 48.0,
            "cores": 14,
            "ram_gb": 64,
            "gpus": 0,
            "egress_fee_usd": 0.0,
            "typical_cloud": "Hetzner Cloud / Bare-Metal",
        },
        "aws_spot_c6i": {
            "name": "AWS c6i.4xlarge Spot Instance (16 vCPU / 32GB RAM)",
            "monthly_cost_usd": 72.0,
            "cores": 16,
            "ram_gb": 32,
            "gpus": 0,
            "egress_fee_usd": 15.0,
            "typical_cloud": "Amazon Web Services (EC2 Spot)",
        },
        "runpod_rtx4090": {
            "name": "RunPod Secure Cloud (RTX 4090 24GB / 8 vCPU)",
            "monthly_cost_usd": 155.0,
            "cores": 8,
            "ram_gb": 32,
            "gpus": 1,
            "egress_fee_usd": 0.0,
            "typical_cloud": "RunPod GPU Cloud",
        },
        "ovh_vps": {
            "name": "OVH VPS Elite (8 vCPU / 32GB RAM)",
            "monthly_cost_usd": 38.0,
            "cores": 8,
            "ram_gb": 32,
            "gpus": 0,
            "egress_fee_usd": 0.0,
            "typical_cloud": "OVHcloud Virtual Private Server",
        },
    }

    def calculate_cloud_arbitrage_roi(
        self,
        preset_key: str = "hetzner_dedicated",
        utilization_percent: float = 65.0,
        overcommit_ratio: float = 2.5,
        custom_cost_usd: float | None = None,
        custom_cores: int | None = None,
        custom_gpus: int | None = None,
    ) -> dict:
        """Calculate monthly revenue, net profit margin, and ROI for renting a cloud machine and hosting it on DCCN."""
        preset = self.CLOUD_PRESETS.get(preset_key, self.CLOUD_PRESETS["hetzner_dedicated"])
        
        monthly_cost = custom_cost_usd if custom_cost_usd is not None and custom_cost_usd > 0 else preset["monthly_cost_usd"]
        cores = custom_cores if custom_cores is not None and custom_cores > 0 else preset["cores"]
        gpus = custom_gpus if custom_gpus is not None and custom_gpus >= 0 else preset["gpus"]

        # Hours per month = 720
        hours_per_month = 720.0
        util_factor = max(0.1, min(1.0, utilization_percent / 100.0))

        # Effective billable capacity using DCCN fractional overcommit (e.g. 2.5x)
        effective_vcpus = cores * overcommit_ratio

        # DCCN base pricing: 10 credits/vCPU-hr, 50 credits/GPU-hr
        # 100 DCCN Credits = $1.00 USD (0.01 USD/credit)
        hourly_gross_credits = (effective_vcpus * 10.0 * 0.70) + (gpus * 50.0 * 0.80)  # average clearing price
        monthly_gross_credits = hourly_gross_credits * hours_per_month * util_factor
        
        # Provider yield = 85% of gross credits
        monthly_provider_credits = monthly_gross_credits * 0.85
        monthly_provider_yield_usd = round(monthly_provider_credits / 100.0, 2)

        # Net profit after paying cloud provider rental bill
        monthly_net_profit_usd = round(monthly_provider_yield_usd - monthly_cost, 2)
        net_margin_percent = round((monthly_net_profit_usd / monthly_cost) * 100.0, 1) if monthly_cost > 0 else 0.0

        # Equivalent AWS retail price for the same compute capacity
        aws_equivalent_monthly_usd = round((effective_vcpus * 0.040 * hours_per_month * util_factor) + (gpus * 1.00 * hours_per_month * util_factor), 2)
        client_savings_vs_aws_percent = round(max(0.0, 1.0 - (monthly_provider_yield_usd / max(aws_equivalent_monthly_usd, 1.0))) * 100.0, 1)

        return {
            "preset_key": preset_key,
            "preset_name": preset["name"],
            "underlying_cloud": preset["typical_cloud"],
            "inputs": {
                "monthly_cloud_rental_cost_usd": monthly_cost,
                "hardware_cores": cores,
                "effective_overcommit_vcpus": round(effective_vcpus, 1),
                "gpus": gpus,
                "cluster_utilization_percent": utilization_percent,
                "overcommit_ratio": overcommit_ratio,
            },
            "financials": {
                "monthly_gross_credits_generated": round(monthly_gross_credits, 1),
                "monthly_provider_yield_credits": round(monthly_provider_credits, 1),
                "monthly_provider_yield_usd": monthly_provider_yield_usd,
                "monthly_cloud_expense_usd": monthly_cost,
                "monthly_net_profit_usd": monthly_net_profit_usd,
                "roi_margin_percent": net_margin_percent,
                "profitable": monthly_net_profit_usd > 0,
            },
            "market_disruption": {
                "aws_equivalent_cost_usd": aws_equivalent_monthly_usd,
                "client_savings_vs_aws_percent": client_savings_vs_aws_percent,
                "summary": f"Provider earns ${monthly_net_profit_usd}/mo net profit (+{net_margin_percent}% ROI) while DCCN clients save {client_savings_vs_aws_percent}% vs AWS!",
            },
        }


# Global singleton instance
spot_market_service = SpotMarketService()
