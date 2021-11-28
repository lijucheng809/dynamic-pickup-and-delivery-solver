import pandas as pd
import json


if __name__ == "__main__":
    with open("/Users/lijucheng/Desktop/dynamic-pickup-and-delivery-solver/simulator/dpdp_competition/algorithm/data/route_map/route_cost_map.json", "r") as f:
        route_cost_map = json.load(f)
    with open("/Users/lijucheng/Desktop/dynamic-pickup-and-delivery-solver/simulator/dpdp_competition/algorithm/data/route_map/route_cost_map_1.json", "r") as f:
        route_cost_map_new = json.load(f)
    route_info_df = pd.read_csv("/Users/lijucheng/Desktop/dynamic-pickup-and-delivery-solver/simulator/dpdp_competition/benchmark/route_info.csv")
    n, m = route_info_df.shape
    for i in range(n):
        id = route_info_df.iloc[i]["start_factory_id"] + route_info_df.iloc[i]["end_factory_id"]
        route_cost_map[id]["distance"] = route_info_df.iloc[i]["distance"]
        route_cost_map[id]["travel_time"] = route_info_df.iloc[i]["time"]
    with open("/Users/lijucheng/Desktop/dynamic-pickup-and-delivery-solver/simulator/dpdp_competition/algorithm/data/route_map/route_cost_map_test.json", "w") as f:
        json.dump(route_cost_map, f, indent=4)
