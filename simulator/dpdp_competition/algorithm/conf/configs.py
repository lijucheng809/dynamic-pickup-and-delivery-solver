import os
from simulator.dpdp_competition.algorithm.src.enum.constrain_enum import ConstrainEnum


class Configs(object):
    root_folder_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    algorithm_folder_path = os.path.join(root_folder_path, "algorithm")
    algorithm_data_path = os.path.join(algorithm_folder_path, "data")
    algorithm_data_customer_path = os.path.join(algorithm_data_path, "customer")
    algorithm_data_route_map_path = os.path.join(algorithm_data_path, "route_map")
    customer_info_path = os.path.join(algorithm_data_customer_path, "customer_info.json")

    route_cost_map_path = os.path.join(algorithm_data_route_map_path, "route_cost_map.json")
    data_interaction_folder_path = os.path.join(algorithm_folder_path, "data_interaction")

    vehicle_info_path = os.path.join(data_interaction_folder_path, "vehicle_info.json")
    ongoing_items_path = os.path.join(data_interaction_folder_path, "ongoing_order_items.json")
    unallocated_order_items_path = os.path.join(data_interaction_folder_path, "unallocated_order_items.json")
    output_destination_path = os.path.join(data_interaction_folder_path, "output_destination.json")
    output_route_path = os.path.join(data_interaction_folder_path, "output_route.json")
    middle_vehicle_info_path = os.path.join(data_interaction_folder_path, "middle_vehicle_info.json")
    time_out_requests = os.path.join(data_interaction_folder_path, "time_out_requests.json")

    date = "1900-01-01"
    time = "0:0:0"

    time_2_go = 10
    static_process_time_on_customer = 1800
    shaw_removal_distance_weight = 9
    shaw_removal_travel_time_weight = 3
    shaw_removal_demand_weight = 3
    shaw_removal_vehicle_matched_weight = 5
    alns_segment_size = 100
    alns_min_request_remove_number = 4
    alns_request_remove_number_upperbound = 100
    alns_found_best = 6
    alns_better_than_current = 3
    alns_worst_than_current = 1
    alns_none_improve_iteration = 25
    alns_regret_operator_degree = 2
    algo_run_time = 15


    weighted_objective_function = 1
    shaw_removal_randomness_value = 4
    worst_removal_randomness_value = 2
    sa_cool_rate = 0.99975
    alns_request_remove_number_coff = 0.4
    alns_reaction_parameter = 0.3

    vehicle_capacity = 15

    constrains = {ConstrainEnum.bin_packing: True,
                  ConstrainEnum.capacity: True,
                  ConstrainEnum.time_window: True,
                  ConstrainEnum.port_resource: False,
                  ConstrainEnum.lifo: True,
                  ConstrainEnum.incompatible_items: False,
                  ConstrainEnum.incompatible_item_vehicle: False}
    heuristic_engine = True


if __name__ == "__main__":
    pass
