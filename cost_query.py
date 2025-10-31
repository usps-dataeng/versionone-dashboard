

import csv
import os

# === CONFIG ===
output_path = r"C:\Users\tbh2j0\OneDrive - USPS\Test Folder\edl_vm_optimization_summary.csv"

# === VM Data ===
vm_data = [
    ["Standard_L32s_v3", 73, 148359.36, "Yes", "No", 96934.51, 1163214.12],
    ["Standard_L16s_v3", 35, 36610.00, "Yes", "No", 23940.00, 287280.00],
    ["Standard_D8ads_v5", 24, 7510.80, "Yes", "No", 5638.80, 67665.60],
    ["Standard_E16s_v4", 22, 9906.60, "Yes", "No", 7530.60, 90367.20],
    ["Standard_F16", 20, 7378.80, "Yes", "No", 5538.80, 66465.60],
    ["Standard_E8ds_v4", 8, 2152.00, "Yes", "No", 1616.00, 19392.00],
    ["Standard_E8s_v3", 7, 1568.56, "Yes", "No", 1176.56, 14118.72],
    ["Standard_DS15_v2", 5, 2697.40, "Yes", "No", 2022.40, 24268.80],
    ["Standard_F64s_v2", 4, 5221.16, "Yes", "No", 3917.16, 47005.92],
    ["Standard_E32s_v3", 2, 1795.46, "Yes", "No", 1355.46, 16265.52],
    ["Standard_E32ds_v4", 1, 1345.94, "Yes", "No", 1009.94, 12119.28],
    ["Standard_D16ads_v5", 1, 312.95, "Yes", "No", 234.95, 2819.40],
    ["Standard_L8s_v3", 1, 508.00, "Yes", "No", 332.00, 3984.00],
    ["Standard_E8s_v4", 1, 233.34, "Yes", "No", 175.34, 2104.08],
    ["Standard_E16s_v3", 1, 450.30, "Yes", "No", 342.30, 4107.60],
]

# === Determine Recommended SKU ===
def recommend_sku(vm_size):
    if vm_size.startswith("Standard_L") or vm_size.startswith("Standard_E"):
        return "Spot"
    elif vm_size.startswith("Standard_D") or vm_size.startswith("Standard_F"):
        return "Resize"
    else:
        return "Reserved"

# === Write CSV ===
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, mode="w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["VM Size", "Count", "Total Cost", "Spot Eligible", "Already Spot", "Monthly Savings", "Annual Savings", "Recommended SKU"])
    for row in vm_data:
        recommended = recommend_sku(row[0])
        writer.writerow(row + [recommended])

print(f"✅ CSV saved to: {output_path}")
