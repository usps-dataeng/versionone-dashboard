import csv
import os
import pandas as pd
import ast

# === CONFIG ===
resource_graph_path = r"C:\Users\tbh2j0\OneDrive - USPS\Test Folder\AzureResourceGraphResults_Query_1.csv"
optimization_summary_path = r"C:\Users\tbh2j0\OneDrive - USPS\Test Folder\edl_vm_optimization_summary.csv"
output_path = r"C:\Users\tbh2j0\OneDrive - USPS\Test Folder\vm_job_savings_by_cluster.csv"

# === LOAD RESOURCE GRAPH ===
df_rg = pd.read_csv(resource_graph_path)

# === EXTRACT TAGS ===
def extract_tag_value(tag_str, key):
    try:
        tag_dict = ast.literal_eval(tag_str)
        return tag_dict.get(key, "")
    except (ValueError, SyntaxError):
        return ""

df_rg["ClusterId"] = df_rg["tags"].apply(lambda x: extract_tag_value(x, "ClusterId"))
df_rg["RunName"] = df_rg["tags"].apply(lambda x: extract_tag_value(x, "RunName"))
df_rg["Creator"] = df_rg["tags"].apply(lambda x: extract_tag_value(x, "Creator"))
df_rg["VM Size"] = df_rg["properties_hardwareProfile_vmSize"]
df_rg["Resource Group"] = df_rg["resourceGroup"]

# === Fallback: Use ClusterId if RunName is missing ===
df_rg["RunName"] = df_rg.apply(
    lambda row: row["RunName"] if row["RunName"] else row["ClusterId"],
    axis=1
)
df_rg["RunName Missing"] = df_rg["tags"].apply(lambda x: "RunName" not in str(x))

# === LOAD OPTIMIZATION SUMMARY ===
df_opt = pd.read_csv(optimization_summary_path)

# === CLEAN AND CONVERT TO NUMERIC ===
for col in ["Monthly Savings", "Annual Savings", "Total Cost"]:
    df_opt[col] = (
        df_opt[col]
        .astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .astype(float)
    )

df_opt["Count"] = pd.to_numeric(df_opt["Count"], errors="coerce")

# === ADD PER-VM METRICS ===
df_opt["Monthly Savings Per VM"] = df_opt["Monthly Savings"] / df_opt["Count"]
df_opt["Annual Savings Per VM"] = df_opt["Annual Savings"] / df_opt["Count"]
df_opt["Total Cost Per VM"] = df_opt["Total Cost"] / df_opt["Count"]

# === ADD RECOMMENDED SKU AND NEW SIZE ===
def recommend_sku(vm_size):
    if vm_size.startswith("Standard_L") or vm_size.startswith("Standard_E"):
        return "Spot"
    elif vm_size.startswith("Standard_D") or vm_size.startswith("Standard_F"):
        return "Resize"
    else:
        return "Reserved"

resize_map = {
    "Standard_D8ads_v5": "Standard_B8ps_v2",
    "Standard_F16": "Standard_B4ms",
    "Standard_DS15_v2": "Standard_B4ms",
    "Standard_D16ads_v5": "Standard_E4ps_v6",
}

df_opt["Recommended SKU"] = df_opt["VM Size"].apply(recommend_sku)
df_opt["New SKU size"] = df_opt["VM Size"].apply(lambda x: resize_map.get(x, ""))

# === JOIN ON VM SIZE ===
df_joined = pd.merge(df_rg, df_opt, on="VM Size", how="inner")

# === AGGREGATE BY CLUSTER ===
grouped = df_joined.groupby([
    "Resource Group", "ClusterId", "RunName", "Creator", "VM Size", "Recommended SKU", "New SKU size"
]).agg({
    "Monthly Savings Per VM": "sum",
    "Annual Savings Per VM": "sum",
    "Total Cost Per VM": "sum"
})

grouped["VM Count"] = df_joined.groupby([
    "Resource Group", "ClusterId", "RunName", "Creator", "VM Size", "Recommended SKU", "New SKU size"
]).size()

grouped = grouped.reset_index()

# === CALCULATE % SAVINGS ===
grouped["Current Cost"] = grouped["Total Cost Per VM"]
grouped["% Savings"] = (grouped["Monthly Savings Per VM"] / grouped["Current Cost"]) * 100

# === FORMAT CURRENCY AND PERCENT ===
grouped["Monthly Savings"] = grouped["Monthly Savings Per VM"].apply(lambda x: f"${x:,.2f}")
grouped["Annual Savings"] = grouped["Annual Savings Per VM"].apply(lambda x: f"${x:,.2f}")
grouped["Current Cost"] = grouped["Current Cost"].apply(lambda x: f"${x:,.2f}")
grouped["% Savings"] = grouped["% Savings"].apply(lambda x: f"{x:.1f}%")

grouped.drop(columns=["Monthly Savings Per VM", "Annual Savings Per VM", "Total Cost Per VM"], inplace=True)

# === SAVE TO CSV ===
os.makedirs(os.path.dirname(output_path), exist_ok=True)
grouped.to_csv(output_path, index=False)

print(f"✅ Cluster-level savings report saved to: {output_path}")

# === OPTIONAL: Print rows missing RunName ===
missing_runname = df_rg[df_rg["RunName Missing"]]
print(missing_runname[["resourceGroup", "ClusterId", "Creator", "tags"]])
