import os


class configs(object):
    root_folder_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    algorithm_folder_path = os.path.join(root_folder_path, "algorithm")
    config_ini_path = os.path.join(algorithm_folder_path, "src\config\config.ini")
    customer_info_path = os.path.join(algorithm_folder_path,
                                      "data\dynamic_pickup_and_delivery_testdata\customer\customer_info.json")

    route_cost_map_path = os.path.join(algorithm_folder_path,
                                      "data\dynamic_pickup_and_delivery_testdata\\route_map\\route_cost_map.json")
    data_interaction_folder_path = os.path.join(algorithm_folder_path, "data_interaction")

    vehicle_info_path = os.path.join(data_interaction_folder_path, "vehicle_info.json")
    ongoing_items_path = os.path.join(data_interaction_folder_path, "ongoing_order_items.json")
    unallocated_order_items_path = os.path.join(data_interaction_folder_path, "unallocated_order_items.json")
    output_destination_path = os.path.join(data_interaction_folder_path, "output_destination.json")
    output_route_path = os.path.join(data_interaction_folder_path, "output_route.json")
