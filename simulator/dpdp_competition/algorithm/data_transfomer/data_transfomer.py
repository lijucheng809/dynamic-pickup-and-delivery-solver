import json
import time
from datetime import datetime, timedelta
from copy import deepcopy
import os

from simulator.dpdp_competition.algorithm.conf.configs import Configs
from simulator.dpdp_competition.algorithm.src.enum.constrain_enum import ConstrainEnum
from simulator.dpdp_competition.algorithm.src.enum.request_info_enum import RequestInfoEnum
from simulator.dpdp_competition.algorithm.src.enum.item_info_enum import ItemInfoEnum
from simulator.dpdp_competition.algorithm.src.enum.vehicle_info_enum import VehicleInfoEnum
from simulator.dpdp_competition.algorithm.src.enum.destination_info_enum import DestinationInfoEnum
from simulator.dpdp_competition.algorithm.src.enum.package_enum import PackageEnum
from simulator.dpdp_competition.algorithm.src.enum.demand_type_enum import DemandTypeEnum


class DataTransformer(object):
    @staticmethod
    def __gen_kid_request(requestID, request, items_map, request_item_map, spilt_num=5):
        q_standard_split_num = len(request_item_map["q_standard"]) // spilt_num
        q_small_split_num = len(request_item_map["q_small"]) // spilt_num
        q_box_split_num = len(request_item_map["q_box"]) // spilt_num
        kid_requests = {}
        kid_request_item_map = {}
        kid_q_standard_num_list, kid_q_small_num_list, kid_q_box_num_list = [0.] * spilt_num, [0.] * spilt_num, [
            0.] * spilt_num
        for i in range(spilt_num):
            if i < spilt_num - 1:
                kid_q_standard_num_list[i] = q_standard_split_num
                kid_q_small_num_list[i] = q_small_split_num
                kid_q_box_num_list[i] = q_box_split_num
            else:
                if q_standard_split_num != 0:
                    kid_q_standard_num_list[i] = len(request_item_map["q_standard"]) - (
                            spilt_num - 1) * q_standard_split_num
                if q_small_split_num != 0:
                    kid_q_small_num_list[i] = len(request_item_map["q_small"]) - (spilt_num - 1) * q_small_split_num
                if q_box_split_num != 0:
                    kid_q_box_num_list[i] = len(request_item_map["q_box"]) - (spilt_num - 1) * q_box_split_num
        for i in range(spilt_num):
            kid_requestID = requestID + "-{}".format(i + 1)
            kid_requests[kid_requestID] = deepcopy(request)
            kid_requests[kid_requestID][RequestInfoEnum.pallets.name]["q_standard"] = kid_q_standard_num_list[i]
            kid_requests[kid_requestID][RequestInfoEnum.pallets.name]["q_small"] = 0.5 * kid_q_small_num_list[i]
            kid_requests[kid_requestID][RequestInfoEnum.pallets.name]["q_box"] = 0.25 * kid_q_box_num_list[i]
            process_time = 0
            if i < spilt_num - 1:
                if request_item_map["q_standard"] and q_standard_split_num != 0:
                    q_standard_items_id = request_item_map["q_standard"][
                                          i * q_standard_split_num:(i + 1) * q_standard_split_num]
                else:
                    q_standard_items_id = []
                if request_item_map["q_small"] and q_small_split_num != 0:
                    q_small_items_id = request_item_map["q_small"][i * q_small_split_num:(i + 1) * q_small_split_num]
                else:
                    q_small_items_id = []
                if request_item_map["q_box"] and q_box_split_num != 0:
                    q_box_items_id = request_item_map["q_box"][i * q_box_split_num:(i + 1) * q_box_split_num]
                else:
                    q_box_items_id = []
                if i == 0:
                    if q_standard_split_num == 0 and request_item_map["q_standard"]:
                        q_standard_items_id = request_item_map["q_standard"]
                        kid_requests[kid_requestID][RequestInfoEnum.pallets.name]["q_standard"] += len(
                            request_item_map["q_standard"])
                    if q_small_split_num == 0 and request_item_map["q_small"]:
                        q_small_items_id = request_item_map["q_small"]
                        kid_requests[kid_requestID][RequestInfoEnum.pallets.name]["q_small"] += 0.5 * len(
                            request_item_map["q_small"])
                    if q_box_split_num == 0 and request_item_map["q_box"]:
                        q_box_items_id = request_item_map["q_box"]
                        kid_requests[kid_requestID][RequestInfoEnum.pallets.name]["q_box"] += 0.25 * len(
                            request_item_map["q_box"])
                kid_request_item_map[kid_requestID] = {"q_standard": q_standard_items_id,
                                                       "q_small": q_small_items_id,
                                                       "q_box": q_box_items_id}

            else:
                if request_item_map["q_standard"] and q_standard_split_num != 0:
                    q_standard_items_id = request_item_map["q_standard"][(spilt_num - 1) * q_standard_split_num:]
                else:
                    q_standard_items_id = []
                if request_item_map["q_small"] and q_small_split_num != 0:
                    q_small_items_id = request_item_map["q_small"][(spilt_num - 1) * q_small_split_num:]
                else:
                    q_small_items_id = []
                if request_item_map["q_box"] and q_box_split_num != 0:
                    q_box_items_id = request_item_map["q_box"][(spilt_num - 1) * q_box_split_num:]
                else:
                    q_box_items_id = []
                kid_request_item_map[kid_requestID] = {"q_standard": q_standard_items_id,
                                                       "q_small": q_small_items_id,
                                                       "q_box": q_box_items_id}
            kid_items = q_small_items_id + q_standard_items_id + q_box_items_id
            for item_id in kid_items:
                process_time += items_map[item_id]["load_time"]
            kid_requests[kid_requestID][RequestInfoEnum.process_time.name] = process_time
            kid_requests[kid_requestID][RequestInfoEnum.demand.name] = \
            kid_requests[kid_requestID][RequestInfoEnum.pallets.name]["q_standard"] + \
            kid_requests[kid_requestID][RequestInfoEnum.pallets.name]["q_small"] + \
            kid_requests[kid_requestID][RequestInfoEnum.pallets.name]["q_box"]

            # todo 考虑装箱约束进行拆分bin

        return {"kid_requests": kid_requests,
                "kid_request_item_map": kid_request_item_map}

    @staticmethod
    def __demand_split(big_requests: set, requests: dict, items_map: dict, requests_items_map: dict,
                       items_requests_map: dict):
        temp_requests = {}
        for requestID in big_requests:
            temp_requests[requestID] = requests[requestID]
            new_requests = DataTransformer.__gen_kid_request(requestID, requests[requestID], items_map,
                                                             requests_items_map[requestID])
            requests.update(new_requests["kid_requests"])
            requests_items_map.update(new_requests["kid_request_item_map"])
            for request_id in new_requests["kid_request_item_map"]:
                for tp in new_requests["kid_request_item_map"][request_id]:
                    for item_id in new_requests["kid_request_item_map"][request_id][tp]:
                        items_requests_map[item_id] = request_id
            requests_items_map.pop(requestID)
            requests.pop(requestID)

    @staticmethod
    def __gen_time_stamp(arrive_time: datetime, leave_time: datetime, update_time):
        arrive_time = time.mktime(arrive_time.timetuple())
        leave_time = time.mktime(leave_time.timetuple())
        return arrive_time, leave_time

    @staticmethod
    def __reset_destination(vehicles_info_map, vehicleID, customers, destination, depot_node, update_time):
        factory_id = vehicles_info_map[vehicleID]["destination"]["factory_id"]
        lng, lat = customers[factory_id].getPosition[0], customers[factory_id].getPosition[1]
        destination[vehicleID] = vehicles_info_map[vehicleID]["destination"]
        destination[vehicleID]["lng"] = lng
        destination[vehicleID]["lat"] = lat
        arrive_time = depot_node.vehicleArriveTime
        leave_time = depot_node.vehicleDepartureTime
        arrive_time, leave_time = DataTransformer.__gen_time_stamp(arrive_time, leave_time, update_time)
        destination[vehicleID]["arrive_time"] = arrive_time
        destination[vehicleID]["leave_time"] = leave_time
        destination[vehicleID]["delivery_item_list"] = []
        destination[vehicleID]["pickup_item_list"] = []

    @staticmethod
    def requests_sim_2_algo(vehicle_capacity=15):
        with open(Configs.unallocated_order_items_path) as f:
            orders = json.load(f)
        big_requests = set()
        requests_items_map = {}
        requests = {}
        items_map = {}
        items_requests_map = {}
        for item in orders:
            items_requests_map[item[ItemInfoEnum.id.name]] = item[ItemInfoEnum.order_id.name]
            items_map[item[ItemInfoEnum.id.name]] = item
            if item[ItemInfoEnum.order_id.name] not in requests:
                creation_time = time.strftime("%Y-%m-%d %H:%M:%S",
                                              time.localtime(item[RequestInfoEnum.creation_time.name]))
                latest_leave_time = str(datetime.strptime(creation_time, "%Y-%m-%d %H:%M:%S") + timedelta(hours=4))
                # latest_leave_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item["committed_completion_time"]))
                requests_items_map[item[ItemInfoEnum.order_id.name]] = {PackageEnum.q_standard.name: [],
                                                                        PackageEnum.q_small.name: [],
                                                                        PackageEnum.q_box.name: []}
                pickup_timeWindow = [creation_time, latest_leave_time]
                delivery_timeWindow = [creation_time, latest_leave_time]
                pallets = {PackageEnum.q_standard.name: 0, PackageEnum.q_small.name: 0, PackageEnum.q_box.name: 0}
                demand = 0
                process_time = 0
                pickup_customer_id = item[ItemInfoEnum.pickup_factory_id.name]
                delivery_customer_id = item[ItemInfoEnum.delivery_factory_id.name]
                requests[item[ItemInfoEnum.order_id.name]] = {RequestInfoEnum.pallets.name: pallets,
                                                              RequestInfoEnum.demand.name: demand,
                                                              RequestInfoEnum.creation_time.name: creation_time,
                                                              RequestInfoEnum.pickup_timeWindow.name: pickup_timeWindow,
                                                              RequestInfoEnum.delivery_timeWindow.name: delivery_timeWindow,
                                                              RequestInfoEnum.process_time.name: process_time,
                                                              RequestInfoEnum.pickup_customer_id.name: pickup_customer_id,
                                                              RequestInfoEnum.delivery_customer_id.name: delivery_customer_id}
                if Configs.constrains[ConstrainEnum.bin_packing]:
                    requests[item[ItemInfoEnum.order_id.name]][RequestInfoEnum.bin_dimension.name] = []
                # todo 原则上一份订单中，不应该存在不兼容的货物， 待核实
                if Configs.constrains[ConstrainEnum.incompatible_items]:
                    requests[item[ItemInfoEnum.order_id.name]][RequestInfoEnum.incompatible_item_type_list.name] = set(
                        item[ItemInfoEnum.incompatible_items.name])
                if Configs.constrains[ConstrainEnum.incompatible_items] or Configs.constrains[ConstrainEnum.incompatible_item_vehicle]:
                    requests[item[ItemInfoEnum.order_id.name]][RequestInfoEnum.item_type.name] = item[ItemInfoEnum.item_type.name]
            if Configs.constrains[ConstrainEnum.bin_packing]:
                requests[item[ItemInfoEnum.order_id.name]][RequestInfoEnum.bin_dimension.name].append(item[ItemInfoEnum.dimension.name])
            # todo 原则上一份订单中，不应该存在不兼容的货物， 待核实
            # todo 随着包装类型的增多，需要增加多个if else判断
            if Configs.constrains[ConstrainEnum.incompatible_items]:
                requests[item[ItemInfoEnum.order_id.name]][RequestInfoEnum.incompatible_item_type_list.name] \
                    = requests[item[ItemInfoEnum.order_id.name]][RequestInfoEnum.incompatible_item_type_list.name].union(
                    set(item[RequestInfoEnum.incompatible_item_type_list.name]))
            if item[ItemInfoEnum.type.name] == "PALLET":
                requests[item[ItemInfoEnum.order_id.name]][RequestInfoEnum.pallets.name][PackageEnum.q_standard.name] += item[
                    RequestInfoEnum.demand.name]
                requests_items_map[item[ItemInfoEnum.order_id.name]][PackageEnum.q_standard.name].append(item[ItemInfoEnum.id.name])
            elif item[ItemInfoEnum.type.name] == "HALF_PALLET":
                requests[item[ItemInfoEnum.order_id.name]][RequestInfoEnum.pallets.name][PackageEnum.q_small.name] += item[RequestInfoEnum.demand.name]
                requests_items_map[item[ItemInfoEnum.order_id.name]][PackageEnum.q_small.name].append(item[ItemInfoEnum.id.name])
            else:
                requests[item[ItemInfoEnum.order_id.name]][RequestInfoEnum.pallets.name][PackageEnum.q_box.name] += item[RequestInfoEnum.demand.name]
                requests_items_map[item[ItemInfoEnum.order_id.name]][PackageEnum.q_box.name].append(item[ItemInfoEnum.id.name])
            requests[item[ItemInfoEnum.order_id.name]][RequestInfoEnum.demand.name] += item[RequestInfoEnum.demand.name]
            if requests[item[ItemInfoEnum.order_id.name]][RequestInfoEnum.demand.name] > vehicle_capacity:
                big_requests.add(item[ItemInfoEnum.order_id.name])
            requests[item[ItemInfoEnum.order_id.name]][RequestInfoEnum.process_time.name] += item[ItemInfoEnum.load_time.name]

        # todo 需求拆分对应的装箱约束待完成
        if big_requests:
            DataTransformer.__demand_split(big_requests, requests, items_map, requests_items_map, items_requests_map)

        request_info = {"requests": requests,
                        "items_map": items_map,
                        "requests_items_map": requests_items_map,
                        "items_requests_map": items_requests_map}
        return request_info

    @staticmethod
    def solution_algo_2_sim(vehicles, customers, requests_items_map, vehicles_info_map, old_requests_map):
        vehicle_route = {}
        destination = {}
        vehicleIDs = []
        for vehicleID in vehicles:
            route = vehicles[vehicleID].getCurrentRoute
            vehicle_route[vehicleID] = []
            destination[vehicleID] = None
            update_time = vehicles[vehicleID].getUpdateTime
            if len(route) == 1:
                if vehicles_info_map[vehicleID][VehicleInfoEnum.destination.name]:
                    DataTransformer.__reset_destination(vehicles_info_map, vehicleID, customers, destination, route[0],
                                                        update_time)
                continue
            else:
                n = len(route)
                left, rk = 1, 1
                factory_id = route[1].customerID
                if vehicles_info_map[vehicleID][VehicleInfoEnum.destination.name] and \
                        vehicles_info_map[vehicleID][VehicleInfoEnum.destination.name][DestinationInfoEnum.factory_id.name] != factory_id:
                    DataTransformer.__reset_destination(vehicles_info_map, vehicleID, customers, destination, route[0],
                                                        update_time)
                while left < n:
                    while rk + 1 < n and route[rk + 1].customerID == route[left].customerID:
                        rk += 1
                    factory_id = route[left].customerID
                    lng, lat = customers[factory_id].getPosition[0], customers[factory_id].getPosition[1]
                    arrive_time = route[left].vehicleArriveTime
                    leave_time = route[left].vehicleDepartureTime
                    arrive_time, leave_time = DataTransformer.__gen_time_stamp(arrive_time, leave_time, update_time)
                    delivery_item_list = []
                    pickup_item_list = []
                    for i in range(left, rk + 1):
                        node = route[i]
                        requestID = node.requestID
                        if requestID not in old_requests_map:
                            items = requests_items_map[requestID]
                            if node.demandType == DemandTypeEnum.pickup.name:
                                pickup_item_list += items[PackageEnum.q_standard.name] + items[PackageEnum.q_small.name] \
                                                    + items[PackageEnum.q_box.name]
                            else:
                                if DemandTypeEnum.delivery_only.name in items:
                                    delivery_item_list += items[DemandTypeEnum.delivery_only.name][::-1]
                                else:
                                    total_items = items[PackageEnum.q_standard.name] + items[PackageEnum.q_small.name]\
                                                  + items[PackageEnum.q_box.name]
                                    delivery_item_list += total_items[::-1]
                        else:
                            if node.demandType == DemandTypeEnum.pickup.name:
                                for old_request_id in old_requests_map[requestID]:
                                    items = requests_items_map[old_request_id]
                                    pickup_item_list += items[PackageEnum.q_standard.name] + items[PackageEnum.q_small.name] \
                                                        + items[PackageEnum.q_box.name]
                            else:
                                for old_request_id in old_requests_map[requestID][::-1]:
                                    items = requests_items_map[old_request_id]
                                    total_items = items[PackageEnum.q_standard.name] + items[PackageEnum.q_small.name] \
                                                  + items[PackageEnum.q_box.name]
                                    delivery_item_list += total_items[::-1]
                                # delivery_item_list = delivery_item_list[::-1]
                    customer_info = {"factory_id": factory_id,
                                     "lng": lng,
                                     "lat": lat,
                                     "arrive_time": arrive_time,
                                     "leave_time": leave_time,
                                     "pickup_item_list": pickup_item_list,
                                     "delivery_item_list": delivery_item_list}

                    vehicle_route[vehicleID].append(customer_info)
                    if not destination[vehicleID] and \
                            (not vehicles_info_map[vehicleID][VehicleInfoEnum.destination.name] or
                             vehicles_info_map[vehicleID][VehicleInfoEnum.destination.name][DestinationInfoEnum.factory_id.name] == factory_id):
                        destination[vehicleID] = customer_info
                        vehicleIDs.append(vehicleID)
                    left = rk + 1
                    rk += 1

        for vehicleID in vehicle_route:
            if len(vehicle_route[vehicleID]) > 0:
                if destination[vehicleID][DestinationInfoEnum.pickup_item_list.name] or \
                        destination[vehicleID][DestinationInfoEnum.delivery_item_list.name]:
                    del vehicle_route[vehicleID][0]
        with open(Configs.output_destination_path, "w") as f:
            json.dump(destination, f, indent=4)
        with open(Configs.output_route_path, "w") as f:
            json.dump(vehicle_route, f, indent=4)

        # with open(Configs.vehicle_info_path, "r") as f:
        #     vehicles_info = json.load(f)
        # flag = True
        # for vehicle_info in vehicles_info:
        #     if vehicle_info["destination"]:
        #         flag = False
        #         break
        # vehicle_start_end_pair = {}
        # if flag:
        #     if os.path.exists(Configs.time_out_requests):
        #         os.remove(Configs.time_out_requests)
        #     for vehicle_info in vehicles_info:
        #         start_pos = vehicle_info["cur_factory_id"]
        #         if destination[vehicle_info["id"]]:
        #             end_pos = destination[vehicle_info["id"]]["factory_id"]
        #         else:
        #             end_pos = start_pos
        #         vehicle_start_end_pair[vehicle_info["id"]] = {"start": start_pos, "end": end_pos}
        # else:
        #     with open(Configs.middle_vehicle_info_path, "r") as f:
        #         middle_vehicles_info = json.load(f)
        #     for vehicle_info in vehicles_info:
        #         vehicleID = vehicle_info["id"]
        #         if vehicle_info["cur_factory_id"]:
        #             start_pos = vehicle_info["cur_factory_id"]
        #         else:
        #             start_pos = middle_vehicles_info[vehicleID]["start"]
        #         if destination[vehicle_info["id"]]:
        #             end_pos = destination[vehicle_info["id"]]["factory_id"]
        #         else:
        #             end_pos = start_pos
        #         vehicle_start_end_pair[vehicle_info["id"]] = {"start": start_pos, "end": end_pos}
        #
        # with open(Configs.middle_vehicle_info_path, "w") as f:
        #     json.dump(vehicle_start_end_pair, f, indent=4)


if __name__ == "__main__":
    # __requests_sim_2_algo()
    pass
