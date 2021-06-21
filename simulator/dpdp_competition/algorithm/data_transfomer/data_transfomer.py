import json
import time
from datetime import datetime, timedelta
from simulator.dpdp_competition.algorithm.conf.configs import configs
from copy import deepcopy


def __gen_kid_request(requestID, request, items_map, request_item_map, spilt_num=5):
    q_standard_split_num = len(request_item_map["q_standard"]) // spilt_num
    q_small_split_num = len(request_item_map["q_small"]) // spilt_num
    q_box_split_num = len(request_item_map["q_box"]) // spilt_num
    kid_requests = {}
    kid_request_item_map = {}
    kid_q_standard_num_list, kid_q_small_num_list, kid_q_box_num_list = [0] * spilt_num, [0] * spilt_num, [
        0] * spilt_num
    for i in range(spilt_num):
        if i < spilt_num - 1:
            kid_q_standard_num_list[i] = q_standard_split_num
            kid_q_small_num_list[i] = q_small_split_num
            kid_q_box_num_list[i] = q_box_split_num
        else:
            kid_q_standard_num_list[i] = len(request_item_map["q_standard"]) - (spilt_num-1) * q_standard_split_num
            kid_q_small_num_list[i] = len(request_item_map["q_small"]) - (spilt_num-1) * q_small_split_num
            kid_q_box_num_list[i] = len(request_item_map["q_box"]) - (spilt_num-1) * q_box_split_num
    for i in range(spilt_num):
        kid_requestID = requestID + "-{}".format(i + 1)
        kid_requests[kid_requestID] = deepcopy(request)
        kid_requests[kid_requestID]["pallets"]["q_standard"] = kid_q_standard_num_list[i]
        kid_requests[kid_requestID]["pallets"]["q_small"] = kid_q_small_num_list[i]
        kid_requests[kid_requestID]["pallets"]["q_box"] = kid_q_box_num_list[i]
        process_time = 0
        if i < spilt_num - 1:
            q_standard_items_id = [] if not request_item_map["q_standard"] else request_item_map["q_standard"][
                                                                                i * q_standard_split_num:(
                                                                                                                 i + 1) * q_standard_split_num]
            q_small_items_id = [] if not request_item_map["q_small"] else request_item_map["q_small"][
                                                                          i * q_small_split_num:(
                                                                                                        i + 1) * q_small_split_num]
            q_box_items_id = [] if not request_item_map["q_box"] else request_item_map["q_box"][
                                                                      i * q_box_split_num:(i + 1) * q_box_split_num]
            if i == 0:
                if q_standard_split_num == 0 and request_item_map["q_standard"]:
                    q_standard_items_id = request_item_map["q_standard"]
                if q_small_split_num == 0 and request_item_map["q_small"]:
                    q_small_items_id = request_item_map["q_small"]
                if q_box_split_num == 0 and request_item_map["q_box"]:
                    q_box_items_id = request_item_map["q_box"]
            kid_request_item_map[kid_requestID] = {"q_standard": q_standard_items_id,
                                                   "q_small": q_small_items_id,
                                                   "q_box": q_box_items_id}

        else:
            q_standard_items_id = [] if not request_item_map["q_standard"] else request_item_map["q_standard"][
                                                                                (spilt_num - 1) * q_standard_split_num:]
            q_small_items_id = [] if not request_item_map["q_small"] else request_item_map["q_small"][
                                                                          (spilt_num - 1) * q_small_split_num:]
            q_box_items_id = [] if not request_item_map["q_box"] else request_item_map["q_box"][
                                                                      (spilt_num - 1) * q_box_split_num:]
            kid_request_item_map[kid_requestID] = {"q_standard": q_standard_items_id,
                                                   "q_small": q_small_items_id,
                                                   "q_box": q_box_items_id}
        kid_items = q_small_items_id + q_standard_items_id + q_box_items_id
        for item_id in kid_items:
            process_time += items_map[item_id]["load_time"]
        kid_requests[kid_requestID]["load/unload_time"] = process_time
        kid_requests[kid_requestID]["demand"] = kid_requests[kid_requestID]["pallets"]["q_standard"] + \
                                                kid_requests[kid_requestID]["pallets"]["q_small"] + \
                                                kid_requests[kid_requestID]["pallets"]["q_box"]
    return {"kid_requests": kid_requests,
            "kid_request_item_map": kid_request_item_map}


def __demand_split(big_requests: set, requests: dict, items_map: dict, requests_items_map: dict,
                   items_requests_map: dict):
    temp_requests = {}
    for requestID in big_requests:
        temp_requests[requestID] = requests[requestID]
        new_requests = __gen_kid_request(requestID, requests[requestID], items_map, requests_items_map[requestID])
        requests.update(new_requests["kid_requests"])
        requests_items_map.update(new_requests["kid_request_item_map"])
        for request_id in new_requests["kid_request_item_map"]:
            for tp in new_requests["kid_request_item_map"][request_id]:
                for item_id in new_requests["kid_request_item_map"][request_id][tp]:
                    items_requests_map[item_id] = request_id
        requests_items_map.pop(requestID)
        requests.pop(requestID)


def __requests_sim_2_algo(vehicle_capacity=15):
    with open(configs.unallocated_order_items_path) as f:
        orders = json.load(f)
    big_requests = set()
    requests_items_map = {}
    requests = {}
    items_map = {}
    items_requests_map = {}
    for item in orders:
        items_requests_map[item["id"]] = item["order_id"]
        items_map[item["id"]] = item
        if item["order_id"] not in requests:
            creation_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item["creation_time"]))
            latest_leave_time = str(datetime.strptime(creation_time, "%Y-%m-%d %H:%M:%S") + timedelta(hours=4))
            # latest_leave_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item["committed_completion_time"]))
            requests_items_map[item["order_id"]] = {"q_standard": [], "q_small": [], "q_box": []}
            pickup_timeWindow = [creation_time, latest_leave_time]
            delivery_timeWindow = [creation_time, latest_leave_time]
            pallets = {"q_standard": 0, "q_small": 0, "q_box": 0}
            demand = 0
            process_time = 0
            pickup_customer_id = item['pickup_factory_id']
            delivery_customer_id = item["delivery_factory_id"]
            requests[item["order_id"]] = {"pallets": pallets, "demand": demand, "creation_time": creation_time,
                                          "pickup_timeWindow": pickup_timeWindow,
                                          "delivery_timeWindow": delivery_timeWindow,
                                          "load/unload_time": process_time,
                                          "pickup_customer_id": pickup_customer_id,
                                          "delivery_customer_id": delivery_customer_id}
        if item["type"] == "PALLET":
            requests[item["order_id"]]["pallets"]["q_standard"] += item["demand"]
            requests_items_map[item["order_id"]]["q_standard"].append(item["id"])
        elif item["type"] == "HALF_PALLET":
            requests[item["order_id"]]["pallets"]["q_small"] += item["demand"]
            requests_items_map[item["order_id"]]["q_small"].append(item["id"])
        else:
            requests[item["order_id"]]["pallets"]["q_box"] += item["demand"]
            requests_items_map[item["order_id"]]["q_box"].append(item["id"])
        requests[item["order_id"]]["demand"] += item["demand"]
        if requests[item["order_id"]]["demand"] > vehicle_capacity:
            big_requests.add(item["order_id"])
        requests[item["order_id"]]["load/unload_time"] += item["load_time"]
    if big_requests:
        __demand_split(big_requests, requests, items_map, requests_items_map, items_requests_map)

    request_info = {"requests": requests,
                    "items_map": items_map,
                    "requests_items_map": requests_items_map,
                    "items_requests_map": items_requests_map}
    return request_info


def __gen_time_stamp(arrive_time: datetime, leave_time: datetime, update_time):
    arrive_time = time.mktime(arrive_time.timetuple())
    leave_time = time.mktime(leave_time.timetuple())
    return arrive_time, leave_time


def __reset_destination(vehicles_info_map, vehicleID, customers, destination, depot_node, update_time):
    factory_id = vehicles_info_map[vehicleID]["destination"]["factory_id"]
    lng, lat = customers[factory_id].getPosition[0], customers[factory_id].getPosition[1]
    destination[vehicleID] = vehicles_info_map[vehicleID]["destination"]
    destination[vehicleID]["lng"] = lng
    destination[vehicleID]["lat"] = lat
    arrive_time = depot_node.vehicleArriveTime
    leave_time = depot_node.vehicleDepartureTime
    arrive_time, leave_time = __gen_time_stamp(arrive_time, leave_time, update_time)
    destination[vehicleID]["arrive_time"] = arrive_time
    destination[vehicleID]["leave_time"] = leave_time
    destination[vehicleID]["delivery_item_list"] = []
    destination[vehicleID]["pickup_item_list"] = []


def __solution_algo_2_sim(vehicles, customers, requests_items_map, vehicles_info_map, ongoing_items_map):
    vehicle_route = {}
    destination = {}
    vehicleIDs = []
    for vehicleID in vehicles:
        route = vehicles[vehicleID].getCurrentRoute
        vehicle_route[vehicleID] = []
        destination[vehicleID] = None
        update_time = vehicles[vehicleID].getUpdateTime
        if len(route) == 1:
            if vehicles_info_map[vehicleID]["destination"]:
                __reset_destination(vehicles_info_map, vehicleID, customers, destination, route[0], update_time)
            continue
        else:
            n = len(route)
            left, rk = 1, 1
            factory_id = route[1].customerID
            if vehicles_info_map[vehicleID]["destination"] and \
                    vehicles_info_map[vehicleID]["destination"]["factory_id"] != factory_id:
                __reset_destination(vehicles_info_map, vehicleID, customers, destination, route[0], update_time)
            while left < n:
                while rk + 1 < n and route[rk + 1].customerID == route[left].customerID:
                    rk += 1
                factory_id = route[left].customerID
                lng, lat = customers[factory_id].getPosition[0], customers[factory_id].getPosition[1]
                # TODO 时间戳格式记得要转换
                arrive_time = route[left].vehicleArriveTime
                leave_time = route[left].vehicleDepartureTime
                arrive_time, leave_time = __gen_time_stamp(arrive_time, leave_time, update_time)
                delivery_item_list = []
                pickup_item_list = []
                for i in range(left, rk + 1):
                    node = route[i]
                    requestID = node.requestID
                    items = requests_items_map[requestID]
                    if node.demandType == "pickup":
                        pickup_item_list += items["q_standard"] + items["q_small"] + items["q_box"]
                    else:
                        # TODO 需要加一个if判断delivery_only的出现的情况
                        if "delivery_only" in items:
                            delivery_item_list += items["delivery_only"][::-1]
                        else:
                            total_items = items["q_standard"] + items["q_small"] + items["q_box"]
                            delivery_item_list += total_items[::-1]
                customer_info = {"factory_id": factory_id,
                                 "lng": lng,
                                 "lat": lat,
                                 "arrive_time": arrive_time,
                                 "leave_time": leave_time,
                                 "pickup_item_list": pickup_item_list,
                                 "delivery_item_list": delivery_item_list}

                vehicle_route[vehicleID].append(customer_info)
                if not destination[vehicleID] and \
                        (not vehicles_info_map[vehicleID]["destination"] or
                         vehicles_info_map[vehicleID]["destination"]["factory_id"] == factory_id):
                    destination[vehicleID] = customer_info
                    vehicleIDs.append(vehicleID)
                left = rk + 1
                rk += 1

    for vehicleID in vehicle_route:
        if len(vehicle_route[vehicleID]) > 0:
            if destination[vehicleID]["pickup_item_list"] or destination[vehicleID]["delivery_item_list"]:
                del vehicle_route[vehicleID][0]
    with open(configs.output_destination_path, "w") as f:
        json.dump(destination, f, indent=4)
    with open(configs.output_route_path, "w") as f:
        json.dump(vehicle_route, f, indent=4)

    with open(configs.vehicle_info_path, "r") as f:
        vehicles_info = json.load(f)
    flag = True
    for vehicle_info in vehicles_info:
        if vehicle_info["destination"]:
            flag = False
            break
    vehicle_start_end_pair = {}
    if flag:
        for vehicle_info in vehicles_info:
            start_pos = vehicle_info["cur_factory_id"]
            if destination[vehicle_info["id"]]:
                end_pos = destination[vehicle_info["id"]]["factory_id"]
            else:
                end_pos = start_pos
            vehicle_start_end_pair[vehicle_info["id"]] = {"start": start_pos, "end": end_pos}
    else:
        with open(configs.middle_vehicle_info_path, "r") as f:
            middle_vehicles_info = json.load(f)
        for vehicle_info in vehicles_info:
            vehicleID = vehicle_info["id"]
            if vehicle_info["cur_factory_id"]:
                start_pos = vehicle_info["cur_factory_id"]
            else:
                start_pos = middle_vehicles_info[vehicleID]["start"]
            if destination[vehicle_info["id"]]:
                end_pos = destination[vehicle_info["id"]]["factory_id"]
            else:
                end_pos = start_pos
            vehicle_start_end_pair[vehicle_info["id"]] = {"start": start_pos, "end": end_pos}

    with open(configs.middle_vehicle_info_path, "w") as f:
        json.dump(vehicle_start_end_pair, f, indent=4)


if __name__ == "__main__":
    # __requests_sim_2_algo()
    pass
