"""
Azure VM Multi-Category Optimization Analysis
Identifies VMs eligible for Spot, Resize, and Reserved Instances
Including combinations of multiple optimization opportunities
"""

import pandas as pd
import os
import ast
from typing import Dict, List

# === CONFIGURATION ===
class Config:
    """Centralized configuration for file paths and thresholds"""

    # Input files
    RESOURCE_GRAPH_PATH = r"C:\Users\tbh2j0\OneDrive - USPS\Test Folder\AzureResourceGraphResults_Query_1.csv"
    OPTIMIZATION_SUMMARY_PATH = r"C:\Users\tbh2j0\OneDrive - USPS\Test Folder\edl_vm_optimization_summary.csv"

    # Optional: CPU/Memory utilization data (if available)
    UTILIZATION_PATH = None  # Set to CSV path if you have utilization metrics

    # Pricing files (actual Azure pricing data)
    INSTANCE_PRICE_PATH = r"C:\Users\tbh2j0\OneDrive - USPS\Test Folder\instanceprice.csv"
    CLOUD_PRICE_PATH = r"C:\Users\tbh2j0\OneDrive - USPS\Test Folder\cloudprice.csv"

    # Output files
    OUTPUT_DIR = r"C:\Users\tbh2j0\OneDrive - USPS\Test Folder"
    MULTI_CATEGORY_OUTPUT = os.path.join(OUTPUT_DIR, "vm_multi_optimization_analysis.csv")
    SPOT_OUTPUT = os.path.join(OUTPUT_DIR, "spot_candidates_expanded.csv")
    RESIZE_OUTPUT = os.path.join(OUTPUT_DIR, "resize_candidates_expanded.csv")
    RESERVED_OUTPUT = os.path.join(OUTPUT_DIR, "reserved_instance_candidates.csv")
    SUMMARY_OUTPUT = os.path.join(OUTPUT_DIR, "optimization_summary_by_category.csv")
    PRIORITY_OUTPUT = os.path.join(OUTPUT_DIR, "high_priority_multi_optimization.csv")
    CLUSTER_SUMMARY_OUTPUT = os.path.join(OUTPUT_DIR, "cluster_level_summary.csv")

    # Reserved Instance Criteria
    # VMs running consistently should be considered for RI (1-year or 3-year commitment)
    RESERVED_MIN_UPTIME_DAYS = 30  # VM should be running for at least 30 days
    RESERVED_EXPECTED_RUNTIME_MONTHS = 12  # Expected to run for at least 12 months

    # Resize Criteria (requires utilization data)
    RESIZE_MAX_CPU_PERCENT = 40  # CPU under 40% = oversized
    RESIZE_MAX_MEMORY_PERCENT = 60  # Memory under 60% = oversized

    # Reserved Instance Discount Estimates (typical Azure savings)
    RESERVED_1YR_DISCOUNT = 0.40  # 40% savings
    RESERVED_3YR_DISCOUNT = 0.62  # 62% savings


class DataLoader:
    """Handles loading and initial processing of data files"""

    @staticmethod
    def extract_tag_value(tag_str: str, key: str) -> str:
        """Extract value from Azure tags string"""
        try:
            tag_dict = ast.literal_eval(tag_str) if isinstance(tag_str, str) else {}
            return tag_dict.get(key, "")
        except (ValueError, SyntaxError, TypeError):
            return ""

    @staticmethod
    def load_resource_graph(path: str) -> pd.DataFrame:
        """Load and process Azure Resource Graph data"""
        df = pd.read_csv(path)

        # Extract tags
        df["ClusterId"] = df["tags"].apply(lambda x: DataLoader.extract_tag_value(x, "ClusterId"))
        df["RunName"] = df["tags"].apply(lambda x: DataLoader.extract_tag_value(x, "RunName"))
        df["Creator"] = df["tags"].apply(lambda x: DataLoader.extract_tag_value(x, "Creator"))

        # Standardize columns
        df["VM Size"] = df["properties_hardwareProfile_vmSize"].astype(str).str.strip().str.upper()
        df["Resource Group"] = df["resourceGroup"]
        df["RunName"] = df.apply(lambda row: row["RunName"] if row["RunName"] else row["ClusterId"], axis=1)
        df["Instance ID"] = df["name"]
        df["VM Name"] = df["name"]

        # Parse VM state if available
        if "properties_instanceView_statuses" in df.columns:
            df["Power State"] = df["properties_instanceView_statuses"].apply(
                lambda x: "Running" if "running" in str(x).lower() else "Stopped"
            )
        else:
            df["Power State"] = "Unknown"

        return df

    @staticmethod
    def load_optimization_summary(path: str) -> pd.DataFrame:
        """Load and clean optimization summary data"""
        df = pd.read_csv(path)
        df["VM Size"] = df["VM Size"].astype(str).str.strip().str.upper()

        # Clean numeric columns
        for col in ["Total Cost", "Monthly Savings", "Annual Savings"]:
            if col in df.columns:
                df[col] = (
                    df[col]
                    .astype(str)
                    .str.replace("$", "", regex=False)
                    .str.replace(",", "", regex=False)
                )
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        # Clean count and calculate per-VM metrics
        df["Count"] = pd.to_numeric(df["Count"], errors="coerce").fillna(1)
        df = df[df["Count"] > 0]  # Remove zero-count rows

        df["Total Cost Per VM"] = df["Total Cost"] / df["Count"]
        df["Monthly Savings Per VM"] = df["Monthly Savings"] / df["Count"]
        df["Annual Savings Per VM"] = df["Annual Savings"] / df["Count"]

        # Safe percentage calculation
        df["% Savings"] = df.apply(
            lambda row: (row["Monthly Savings Per VM"] / row["Total Cost Per VM"]) * 100
            if row["Total Cost Per VM"] > 0 else 0,
            axis=1
        )

        return df

    @staticmethod
    def load_pricing_data(instance_price_path: str) -> pd.DataFrame:
        """Load Azure VM pricing data from instanceprice.csv"""
        df = pd.read_csv(instance_price_path)

        # Standardize VM Size column
        df["VM Size"] = df["API Name"].astype(str).str.strip().str.upper()

        # Parse pricing columns - convert hourly to monthly (730 hours/month)
        def parse_price(price_str):
            """Convert hourly price string to monthly cost"""
            if pd.isna(price_str) or price_str == 'unavailable':
                return 0
            try:
                # Remove '$', 'hourly', and convert to float
                price = float(str(price_str).replace('$', '').replace('hourly', '').replace(',', '').strip())
                return price * 730  # Convert hourly to monthly
            except (ValueError, AttributeError):
                return 0

        # Parse all pricing columns
        df["Linux_OnDemand_Monthly"] = df["Linux On Demand cost"].apply(parse_price)
        df["Linux_Reserved_Monthly"] = df["Linux Reserved cost"].apply(parse_price)
        df["Linux_Spot_Monthly"] = df["Linux Spot cost"].apply(parse_price)
        df["Windows_OnDemand_Monthly"] = df["Windows On Demand cost"].apply(parse_price)
        df["Windows_Reserved_Monthly"] = df["Windows Reserved cost"].apply(parse_price)
        df["Windows_Spot_Monthly"] = df["Windows Spot cost"].apply(parse_price)

        return df

    @staticmethod
    def load_utilization(path: str) -> pd.DataFrame:
        """Load VM utilization metrics if available"""
        if path and os.path.exists(path):
            df = pd.read_csv(path)
            # Expected columns: VM Name, Avg CPU %, Avg Memory %, Max CPU %, Max Memory %
            return df
        return None


class OptimizationAnalyzer:
    """Analyzes VMs for optimization opportunities"""

    def __init__(self, df_vms: pd.DataFrame, df_opt: pd.DataFrame, df_pricing: pd.DataFrame = None, df_util: pd.DataFrame = None):
        self.df_vms = df_vms
        self.df_opt = df_opt
        self.df_pricing = df_pricing
        self.df_util = df_util
        self.df_analysis = None

    def analyze(self) -> pd.DataFrame:
        """Perform comprehensive optimization analysis"""

        # Join VMs with optimization data
        df = pd.merge(self.df_vms, self.df_opt, on="VM Size", how="left")

        # Add pricing data if available
        if self.df_pricing is not None:
            df = pd.merge(df, self.df_pricing, on="VM Size", how="left")

        # Add utilization if available
        if self.df_util is not None:
            df = pd.merge(df, self.df_util, on="VM Name", how="left")

        # Initialize optimization flags
        df["Spot Eligible"] = df.get("Spot Eligible", "NO").astype(str).str.upper()
        df["Already Spot"] = df.get("Already Spot", "NO").astype(str).str.upper()

        # Analyze each category
        df["Is_Spot_Candidate"] = self._analyze_spot(df)
        df["Is_Resize_Candidate"] = self._analyze_resize(df)
        df["Is_Reserved_Candidate"] = self._analyze_reserved(df)

        # Count optimization categories
        df["Optimization_Count"] = (
            df["Is_Spot_Candidate"].astype(int) +
            df["Is_Resize_Candidate"].astype(int) +
            df["Is_Reserved_Candidate"].astype(int)
        )

        # Create category labels
        df["Optimization_Categories"] = df.apply(self._build_category_label, axis=1)

        # Calculate potential savings
        df = self._calculate_savings(df)

        # Priority scoring
        df["Priority_Score"] = self._calculate_priority(df)

        # Add Spot Status column
        df["Spot_Status"] = df.apply(self._determine_spot_status, axis=1)

        # Add Savings Opportunity flag
        df["Savings_Opportunity"] = df["Optimization_Count"].apply(
            lambda x: "Yes" if x > 0 else "No"
        )

        self.df_analysis = df
        return df

    def _analyze_spot(self, df: pd.DataFrame) -> pd.Series:
        """Determine if VM is a spot instance candidate"""
        # Eligible if: marked as spot eligible AND not already spot
        return (
            (df["Spot Eligible"] == "YES") &
            (df["Already Spot"] != "YES")
        )

    def _determine_spot_status(self, row: pd.Series) -> str:
        """Determine spot status for reporting"""
        if row["Already Spot"] == "YES":
            return "Already Spot"
        elif row["Spot Eligible"] == "YES":
            return "Eligible"
        else:
            return "Not Eligible"

    def _analyze_resize(self, df: pd.DataFrame) -> pd.Series:
        """Determine if VM is a resize candidate"""
        # Method 1: If utilization data is available
        if self.df_util is not None and "Avg CPU %" in df.columns:
            cpu_threshold = Config.RESIZE_MAX_CPU_PERCENT
            mem_threshold = Config.RESIZE_MAX_MEMORY_PERCENT

            avg_cpu = pd.to_numeric(df.get("Avg CPU %", 100), errors="coerce").fillna(100)
            avg_mem = pd.to_numeric(df.get("Avg Memory %", 100), errors="coerce").fillna(100)

            return (avg_cpu < cpu_threshold) | (avg_mem < mem_threshold)

        # Method 2: If optimization summary has resize recommendations
        if "Resize Eligible" in df.columns:
            return df["Resize Eligible"].astype(str).str.upper() == "YES"

        # Method 3: Look for oversized indicators in VM size naming
        # Large VMs (D64, E96, etc.) might be candidates
        df["Core_Count"] = df["VM Size"].str.extract(r'(\d+)')[0].astype(float)
        return (df["Core_Count"] >= 16) & (df["VM Size"].str.contains("D|E", regex=True))

    def _analyze_reserved(self, df: pd.DataFrame) -> pd.Series:
        """Determine if VM is a reserved instance candidate"""
        # Reserved instances are good for:
        # 1. VMs that are consistently running (not spot candidates)
        # 2. VMs expected to run long-term (12+ months)
        # 3. Production workloads with predictable usage

        # Rule: If not already spot AND running consistently
        is_production = df["RunName"].astype(str).str.contains("prod|production", case=False, na=False)
        is_not_spot_candidate = ~self._analyze_spot(df)
        is_running = df["Power State"] == "Running"

        # If we have uptime data, use it
        if "Uptime_Days" in df.columns:
            has_uptime = df["Uptime_Days"] >= Config.RESERVED_MIN_UPTIME_DAYS
            return is_not_spot_candidate & is_running & has_uptime

        # Otherwise use heuristics
        return is_not_spot_candidate & (is_running | is_production)

    def _build_category_label(self, row: pd.Series) -> str:
        """Build human-readable category label"""
        categories = []
        if row["Is_Spot_Candidate"]:
            categories.append("Spot")
        if row["Is_Resize_Candidate"]:
            categories.append("Resize")
        if row["Is_Reserved_Candidate"]:
            categories.append("Reserved")

        if not categories:
            return "No Optimization"

        return " + ".join(categories)

    def _calculate_savings(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate potential savings for each optimization category"""

        # Determine if we have actual pricing data
        has_pricing = self.df_pricing is not None and "Linux_OnDemand_Monthly" in df.columns

        # Spot savings
        if has_pricing and "Linux_Spot_Monthly" in df.columns:
            # Use actual spot pricing data
            df["Spot_Monthly_Savings"] = df.apply(
                lambda row: (row.get("Linux_OnDemand_Monthly", row["Total Cost Per VM"]) - row.get("Linux_Spot_Monthly", 0))
                if row["Is_Spot_Candidate"] and row.get("Linux_Spot_Monthly", 0) > 0 else 0,
                axis=1
            )
        else:
            # Fallback to optimization summary spot savings
            df["Spot_Monthly_Savings"] = df.apply(
                lambda row: row["Monthly Savings Per VM"] if row["Is_Spot_Candidate"] else 0,
                axis=1
            )

        # Resize savings (estimate 30-50% for oversized VMs)
        df["Resize_Monthly_Savings"] = df.apply(
            lambda row: row["Total Cost Per VM"] * 0.40 if row["Is_Resize_Candidate"] else 0,
            axis=1
        )

        # Reserved savings
        if has_pricing and "Linux_Reserved_Monthly" in df.columns:
            # Use actual reserved instance pricing
            df["Reserved_1Yr_Monthly_Savings"] = df.apply(
                lambda row: (row.get("Linux_OnDemand_Monthly", row["Total Cost Per VM"]) - row.get("Linux_Reserved_Monthly", 0))
                if row["Is_Reserved_Candidate"] and row.get("Linux_Reserved_Monthly", 0) > 0 else 0,
                axis=1
            )
            # Azure typically offers 3-year RI at ~62% off (about 1.55x better than 1-year)
            # Since we only have 1-year pricing, estimate 3-year
            df["Reserved_3Yr_Monthly_Savings"] = df.apply(
                lambda row: row["Reserved_1Yr_Monthly_Savings"] * 1.55
                if row["Is_Reserved_Candidate"] else 0,
                axis=1
            )
        else:
            # Fallback to percentage estimates
            df["Reserved_1Yr_Monthly_Savings"] = df.apply(
                lambda row: row["Total Cost Per VM"] * Config.RESERVED_1YR_DISCOUNT
                if row["Is_Reserved_Candidate"] else 0,
                axis=1
            )
            df["Reserved_3Yr_Monthly_Savings"] = df.apply(
                lambda row: row["Total Cost Per VM"] * Config.RESERVED_3YR_DISCOUNT
                if row["Is_Reserved_Candidate"] else 0,
                axis=1
            )

        # Total potential savings (max of available options)
        # Note: Spot and Reserved are mutually exclusive
        # But Resize can be combined with either
        df["Total_Monthly_Savings"] = df.apply(
            lambda row: (
                max(row["Spot_Monthly_Savings"], row["Reserved_3Yr_Monthly_Savings"]) +
                row["Resize_Monthly_Savings"]
            ),
            axis=1
        )

        df["Total_Annual_Savings"] = df["Total_Monthly_Savings"] * 12

        return df

    def _calculate_priority(self, df: pd.DataFrame) -> pd.Series:
        """Calculate priority score for optimization (higher = more urgent)"""
        priority = pd.Series(0, index=df.index)

        # More categories = higher priority
        priority += df["Optimization_Count"] * 30

        # Higher cost = higher priority
        priority += (df["Total Cost Per VM"] / 100) * 10

        # Higher savings = higher priority
        priority += (df["Total_Monthly_Savings"] / 100) * 20

        # Multi-category bonus
        priority += (df["Optimization_Count"] >= 2).astype(int) * 25

        return priority.round(0).astype(int)

    def generate_reports(self) -> Dict[str, pd.DataFrame]:
        """Generate various report views"""
        df = self.df_analysis

        # Multi-category optimization report (main report)
        multi_cat = df[df["Optimization_Count"] >= 1].copy()
        multi_cat = multi_cat.sort_values("Priority_Score", ascending=False)

        # Spot candidates
        spot = df[df["Is_Spot_Candidate"]].copy()

        # Resize candidates
        resize = df[df["Is_Resize_Candidate"]].copy()

        # Reserved candidates
        reserved = df[df["Is_Reserved_Candidate"]].copy()

        # High priority (2+ categories)
        high_priority = df[df["Optimization_Count"] >= 2].copy()
        high_priority = high_priority.sort_values("Total_Monthly_Savings", ascending=False)

        # Summary by category
        summary = self._create_summary()

        # Cluster-level aggregation
        cluster_summary = self._create_cluster_summary()

        return {
            "multi_category": multi_cat,
            "spot": spot,
            "resize": resize,
            "reserved": reserved,
            "high_priority": high_priority,
            "summary": summary,
            "cluster_summary": cluster_summary
        }

    def _create_summary(self) -> pd.DataFrame:
        """Create summary statistics by optimization category"""
        df = self.df_analysis

        summary_data = []

        # Overall
        summary_data.append({
            "Category": "Total VMs",
            "VM Count": len(df),
            "Total Monthly Cost": df["Total Cost Per VM"].sum(),
            "Potential Monthly Savings": 0,
            "Potential Annual Savings": 0
        })

        # Spot
        spot_vms = df[df["Is_Spot_Candidate"]]
        summary_data.append({
            "Category": "Spot Candidates",
            "VM Count": len(spot_vms),
            "Total Monthly Cost": spot_vms["Total Cost Per VM"].sum(),
            "Potential Monthly Savings": spot_vms["Spot_Monthly_Savings"].sum(),
            "Potential Annual Savings": spot_vms["Spot_Monthly_Savings"].sum() * 12
        })

        # Resize
        resize_vms = df[df["Is_Resize_Candidate"]]
        summary_data.append({
            "Category": "Resize Candidates",
            "VM Count": len(resize_vms),
            "Total Monthly Cost": resize_vms["Total Cost Per VM"].sum(),
            "Potential Monthly Savings": resize_vms["Resize_Monthly_Savings"].sum(),
            "Potential Annual Savings": resize_vms["Resize_Monthly_Savings"].sum() * 12
        })

        # Reserved (1-year)
        reserved_vms = df[df["Is_Reserved_Candidate"]]
        summary_data.append({
            "Category": "Reserved Instance (1-year)",
            "VM Count": len(reserved_vms),
            "Total Monthly Cost": reserved_vms["Total Cost Per VM"].sum(),
            "Potential Monthly Savings": reserved_vms["Reserved_1Yr_Monthly_Savings"].sum(),
            "Potential Annual Savings": reserved_vms["Reserved_1Yr_Monthly_Savings"].sum() * 12
        })

        # Reserved (3-year)
        summary_data.append({
            "Category": "Reserved Instance (3-year)",
            "VM Count": len(reserved_vms),
            "Total Monthly Cost": reserved_vms["Total Cost Per VM"].sum(),
            "Potential Monthly Savings": reserved_vms["Reserved_3Yr_Monthly_Savings"].sum(),
            "Potential Annual Savings": reserved_vms["Reserved_3Yr_Monthly_Savings"].sum() * 12
        })

        # Multi-category (2+)
        multi_vms = df[df["Optimization_Count"] >= 2]
        summary_data.append({
            "Category": "Multi-Category (2+ optimizations)",
            "VM Count": len(multi_vms),
            "Total Monthly Cost": multi_vms["Total Cost Per VM"].sum(),
            "Potential Monthly Savings": multi_vms["Total_Monthly_Savings"].sum(),
            "Potential Annual Savings": multi_vms["Total_Annual_Savings"].sum()
        })

        # Total potential
        all_optimizable = df[df["Optimization_Count"] >= 1]
        summary_data.append({
            "Category": "TOTAL OPTIMIZATION POTENTIAL",
            "VM Count": len(all_optimizable),
            "Total Monthly Cost": all_optimizable["Total Cost Per VM"].sum(),
            "Potential Monthly Savings": all_optimizable["Total_Monthly_Savings"].sum(),
            "Potential Annual Savings": all_optimizable["Total_Annual_Savings"].sum()
        })

        return pd.DataFrame(summary_data)

    def _create_cluster_summary(self) -> pd.DataFrame:
        """Create cluster-level aggregation summary"""
        df = self.df_analysis

        # Group by ClusterId
        cluster_groups = df.groupby("ClusterId").agg({
            "Instance ID": "count",
            "Total Cost Per VM": "sum",
            "Total_Monthly_Savings": "sum",
            "Total_Annual_Savings": "sum",
            "Is_Spot_Candidate": "sum",
            "Is_Resize_Candidate": "sum",
            "Is_Reserved_Candidate": "sum",
            "Optimization_Count": "sum"
        }).reset_index()

        # Rename columns for clarity
        cluster_groups.columns = [
            "Cluster ID",
            "VM Count",
            "Total Monthly Cost",
            "Total Monthly Savings",
            "Total Annual Savings",
            "Spot Candidates",
            "Resize Candidates",
            "Reserved Candidates",
            "Total Optimization Opportunities"
        ]

        # Calculate savings percentage
        cluster_groups["Savings %"] = cluster_groups.apply(
            lambda row: (row["Total Monthly Savings"] / row["Total Monthly Cost"] * 100)
            if row["Total Monthly Cost"] > 0 else 0,
            axis=1
        )

        # Sort by potential savings
        cluster_groups = cluster_groups.sort_values("Total Monthly Savings", ascending=False)

        return cluster_groups


class ReportExporter:
    """Handles exporting reports to CSV files"""

    @staticmethod
    def format_currency(value):
        """Format value as currency"""
        return f"${value:,.2f}"

    @staticmethod
    def format_percent(value):
        """Format value as percentage"""
        return f"{value:.1f}%"

    @staticmethod
    def export_multi_category(df: pd.DataFrame, path: str):
        """Export main multi-category optimization report"""
        output = df[[
            "Resource Group", "ClusterId", "RunName", "Creator",
            "Instance ID", "VM Name", "VM Size", "Power State",
            "Spot_Status", "Savings_Opportunity",
            "Optimization_Categories", "Optimization_Count", "Priority_Score",
            "Total Cost Per VM", "Total_Monthly_Savings", "Total_Annual_Savings",
            "Is_Spot_Candidate", "Spot_Monthly_Savings",
            "Is_Resize_Candidate", "Resize_Monthly_Savings",
            "Is_Reserved_Candidate", "Reserved_1Yr_Monthly_Savings", "Reserved_3Yr_Monthly_Savings"
        ]].copy()

        # Format currency columns
        for col in ["Total Cost Per VM", "Total_Monthly_Savings", "Total_Annual_Savings",
                    "Spot_Monthly_Savings", "Resize_Monthly_Savings",
                    "Reserved_1Yr_Monthly_Savings", "Reserved_3Yr_Monthly_Savings"]:
            output[col] = output[col].apply(ReportExporter.format_currency)

        output.to_csv(path, index=False)
        print(f"✅ Multi-category optimization report: {path}")

    @staticmethod
    def export_high_priority(df: pd.DataFrame, path: str):
        """Export high-priority multi-optimization VMs"""
        output = df[[
            "Resource Group", "VM Name", "VM Size", "Optimization_Categories",
            "Priority_Score", "Total Cost Per VM", "Total_Monthly_Savings", "Total_Annual_Savings"
        ]].copy()

        for col in ["Total Cost Per VM", "Total_Monthly_Savings", "Total_Annual_Savings"]:
            output[col] = output[col].apply(ReportExporter.format_currency)

        output.to_csv(path, index=False)
        print(f"✅ High-priority multi-optimization report: {path}")

    @staticmethod
    def export_summary(df: pd.DataFrame, path: str):
        """Export summary statistics"""
        output = df.copy()

        for col in ["Total Monthly Cost", "Potential Monthly Savings", "Potential Annual Savings"]:
            output[col] = output[col].apply(ReportExporter.format_currency)

        output.to_csv(path, index=False)
        print(f"✅ Summary by category report: {path}")

    @staticmethod
    def export_cluster_summary(df: pd.DataFrame, path: str):
        """Export cluster-level aggregation report"""
        output = df.copy()

        for col in ["Total Monthly Cost", "Total Monthly Savings", "Total Annual Savings"]:
            output[col] = output[col].apply(ReportExporter.format_currency)

        output["Savings %"] = output["Savings %"].apply(ReportExporter.format_percent)

        output.to_csv(path, index=False)
        print(f"✅ Cluster-level summary report: {path}")

    @staticmethod
    def export_category_reports(reports: Dict[str, pd.DataFrame]):
        """Export individual category reports"""

        # Spot candidates
        if len(reports["spot"]) > 0:
            spot = reports["spot"][[
                "Resource Group", "VM Name", "VM Size", "Total Cost Per VM",
                "Spot_Monthly_Savings", "Spot_Status"
            ]].copy()
            spot["Total Cost Per VM"] = spot["Total Cost Per VM"].apply(ReportExporter.format_currency)
            spot["Spot_Monthly_Savings"] = spot["Spot_Monthly_Savings"].apply(ReportExporter.format_currency)
            spot.to_csv(Config.SPOT_OUTPUT, index=False)
            print(f"✅ Spot candidates report: {Config.SPOT_OUTPUT}")

        # Resize candidates
        if len(reports["resize"]) > 0:
            resize = reports["resize"][[
                "Resource Group", "VM Name", "VM Size", "Total Cost Per VM",
                "Resize_Monthly_Savings"
            ]].copy()
            resize["Total Cost Per VM"] = resize["Total Cost Per VM"].apply(ReportExporter.format_currency)
            resize["Resize_Monthly_Savings"] = resize["Resize_Monthly_Savings"].apply(ReportExporter.format_currency)
            resize.to_csv(Config.RESIZE_OUTPUT, index=False)
            print(f"✅ Resize candidates report: {Config.RESIZE_OUTPUT}")

        # Reserved candidates
        if len(reports["reserved"]) > 0:
            reserved = reports["reserved"][[
                "Resource Group", "VM Name", "VM Size", "Total Cost Per VM",
                "Reserved_1Yr_Monthly_Savings", "Reserved_3Yr_Monthly_Savings"
            ]].copy()
            reserved["Total Cost Per VM"] = reserved["Total Cost Per VM"].apply(ReportExporter.format_currency)
            reserved["Reserved_1Yr_Monthly_Savings"] = reserved["Reserved_1Yr_Monthly_Savings"].apply(ReportExporter.format_currency)
            reserved["Reserved_3Yr_Monthly_Savings"] = reserved["Reserved_3Yr_Monthly_Savings"].apply(ReportExporter.format_currency)
            reserved.to_csv(Config.RESERVED_OUTPUT, index=False)
            print(f"✅ Reserved instance candidates report: {Config.RESERVED_OUTPUT}")


def main():
    """Main execution function"""
    print("=" * 80)
    print("Azure VM Multi-Category Optimization Analysis")
    print("=" * 80)

    # Load data
    print("\n📂 Loading data...")
    df_vms = DataLoader.load_resource_graph(Config.RESOURCE_GRAPH_PATH)
    print(f"  - Loaded {len(df_vms)} VMs from Resource Graph")

    df_opt = DataLoader.load_optimization_summary(Config.OPTIMIZATION_SUMMARY_PATH)
    print(f"  - Loaded optimization data for {len(df_opt)} VM sizes")

    # Load pricing data
    df_pricing = None
    if os.path.exists(Config.INSTANCE_PRICE_PATH):
        df_pricing = DataLoader.load_pricing_data(Config.INSTANCE_PRICE_PATH)
        print(f"  - Loaded actual pricing data for {len(df_pricing)} VM sizes")
    else:
        print("  - No pricing file found (using optimization summary data)")

    df_util = DataLoader.load_utilization(Config.UTILIZATION_PATH)
    if df_util is not None:
        print(f"  - Loaded utilization data for {len(df_util)} VMs")
    else:
        print("  - No utilization data provided (using heuristics for resize analysis)")

    # Analyze
    print("\n🔍 Analyzing optimization opportunities...")
    analyzer = OptimizationAnalyzer(df_vms, df_opt, df_pricing, df_util)
    df_analysis = analyzer.analyze()

    # Generate reports
    print("\n📊 Generating reports...")
    reports = analyzer.generate_reports()

    # Print summary statistics
    print("\n" + "=" * 80)
    print("OPTIMIZATION SUMMARY")
    print("=" * 80)
    for _, row in reports["summary"].iterrows():
        print(f"\n{row['Category']}:")
        print(f"  VMs: {row['VM Count']}")
        print(f"  Monthly Cost: {row['Total Monthly Cost']}")
        print(f"  Potential Monthly Savings: {row['Potential Monthly Savings']}")
        print(f"  Potential Annual Savings: {row['Potential Annual Savings']}")

    # Export reports
    print("\n💾 Exporting reports...")
    os.makedirs(Config.OUTPUT_DIR, exist_ok=True)

    ReportExporter.export_multi_category(reports["multi_category"], Config.MULTI_CATEGORY_OUTPUT)
    ReportExporter.export_high_priority(reports["high_priority"], Config.PRIORITY_OUTPUT)
    ReportExporter.export_summary(reports["summary"], Config.SUMMARY_OUTPUT)
    ReportExporter.export_cluster_summary(reports["cluster_summary"], Config.CLUSTER_SUMMARY_OUTPUT)
    ReportExporter.export_category_reports(reports)

    print("\n" + "=" * 80)
    print("✅ Analysis complete!")
    print("=" * 80)

    # Key insights
    print("\n🎯 KEY INSIGHTS:")
    multi_count = len(reports["high_priority"])
    total_annual = reports["summary"][reports["summary"]["Category"] == "TOTAL OPTIMIZATION POTENTIAL"]["Potential Annual Savings"].values[0]

    print(f"  - {multi_count} VMs eligible for 2+ optimizations (HIGH PRIORITY)")
    print(f"  - Total potential annual savings: {total_annual}")
    print(f"  - Review '{Config.PRIORITY_OUTPUT}' for quick wins")


if __name__ == "__main__":
    main()
