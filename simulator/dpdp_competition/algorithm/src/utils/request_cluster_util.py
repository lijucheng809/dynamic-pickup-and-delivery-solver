from datetime import datetime, timedelta

from simulator.dpdp_competition.algorithm.conf.configs import Configs
from simulator.dpdp_competition.algorithm.src.enum.constrain_enum import ConstrainEnum
from simulator.dpdp_competition.algorithm.src.enum.request_info_enum import RequestInfoEnum
from simulator.dpdp_competition.algorithm.src.enum.demand_type_enum import DemandTypeEnum
from simulator.dpdp_competition.algorithm.src.enum.demand_info_enum import DemandInfoEnum
from simulator.dpdp_competition.algorithm.src.enum.package_enum import PackageEnum


class RequestCluster(object):
    @staticmethod
    def new_requests_cluster(requests):
        # todo 需求拆分约束待实现
        request_batch = {}
        new_requests = {}
        new_request_id = 100
        for requestID in requests:
            p_id = requests[requestID][RequestInfoEnum.pickup_customer_id.name]
            d_id = requests[requestID][RequestInfoEnum.delivery_customer_id.name]
            id = p_id + d_id
            tw_right = datetime.strptime(requests[requestID][RequestInfoEnum.pickup_timeWindow.name][1],
                                         "%Y-%m-%d %H:%M:%S")
            creation_time = datetime.strptime(requests[requestID][RequestInfoEnum.creation_time.name],
                                              "%Y-%m-%d %H:%M:%S")
            volume = requests[requestID][RequestInfoEnum.demand.name]
            # todo 互斥订单不能聚类，逻辑待完善
            if id not in request_batch:
                request_batch[id] = {}
            if not request_batch[id]:
                request_batch[id] = {new_request_id: {"old_requestID": [requestID],
                                                      "min_creation_time": creation_time,
                                                      "max_creation_time": creation_time,
                                                      "volume": volume,
                                                      "max_tw_right": tw_right,
                                                      "min_tw_right": tw_right}}
                if Configs.constrains[ConstrainEnum.incompatible_items]:
                    request_batch[id][new_request_id][RequestInfoEnum.incompatible_item_type_list.name] = \
                        requests[requestID][RequestInfoEnum.incompatible_item_type_list.name]
                if Configs.constrains[ConstrainEnum.incompatible_item_vehicle]:
                    request_batch[id][new_request_id][RequestInfoEnum.item_type.name] = requests[requestID][
                        RequestInfoEnum.item_type.name]
                new_request_id += 1
            else:
                cluster_infeasible = True
                # 就一层循环， 瞎搞。。。
                for request_id in request_batch[id]:
                    min_creation_time = min(creation_time, request_batch[id][request_id]["min_creation_time"])
                    max_creation_time = max(creation_time, request_batch[id][request_id]["max_creation_time"])
                    min_tw_right = min(tw_right, request_batch[id][request_id]["min_tw_right"])
                    max_tw_right = max(tw_right, request_batch[id][request_id]["max_tw_right"])

                    # todo 车型的不同，对应的车的容量也不同，逻辑需要完善
                    if volume + request_batch[id][request_id]["volume"] <= Configs.vehicle_capacity and \
                            min_creation_time + timedelta(minutes=120) >= max_creation_time:
                        cluster_infeasible = False
                        if Configs.constrains[ConstrainEnum.incompatible_items]:
                            if requests[requestID][RequestInfoEnum.item_type.name] in request_batch[id][request_id][
                                RequestInfoEnum.incompatible_item_type_list.name]:
                                cluster_infeasible = True
                                break
                        if Configs.constrains[ConstrainEnum.incompatible_item_vehicle]:
                            if requests[requestID][RequestInfoEnum.item_type] != request_batch[id][request_id][
                                RequestInfoEnum.item_type.name]:
                                cluster_infeasible = True
                                break
                        request_batch[id][request_id]["old_requestID"].append(requestID)
                        request_batch[id][request_id]["volume"] += volume
                        request_batch[id][request_id]["min_creation_time"] = min_creation_time
                        request_batch[id][request_id]["max_creation_time"] = max_creation_time
                        request_batch[id][request_id]["min_tw_right"] = min_tw_right
                        request_batch[id][request_id]["max_tw_right"] = max_tw_right
                        if Configs.constrains[ConstrainEnum.incompatible_items]:
                            request_batch[id][request_id][RequestInfoEnum.incompatible_item_type_list.name] = \
                                request_batch[id][request_id][RequestInfoEnum.incompatible_item_type_list.name].union(
                                    requests[requestID][RequestInfoEnum.incompatible_item_type_list.name])
                        break
                if cluster_infeasible:
                    request_batch[id][new_request_id] = {"old_requestID": [requestID],
                                                         "min_creation_time": creation_time,
                                                         "max_creation_time": creation_time,
                                                         "volume": volume,
                                                         "min_tw_right": tw_right,
                                                         "max_tw_right": tw_right}
                    new_request_id += 1
        old_requests_map = {}
        for id in request_batch:
            for request_id in request_batch[id]:
                if len(request_batch[id][request_id]["old_requestID"]) == 1:
                    old_request_id = request_batch[id][request_id]["old_requestID"][0]
                    new_requests[old_request_id] = requests[old_request_id]
                else:
                    old_requests_map[str(request_id)] = request_batch[id][request_id]["old_requestID"]
                    old_request_id_1 = request_batch[id][request_id]["old_requestID"][0]
                    new_request = requests[old_request_id_1]
                    q_standard_num, q_small_num, q_box_num, process_time = 0, 0, 0, 0
                    bin_dimension_list = []
                    demand = 0
                    for old_request_id in request_batch[id][request_id]["old_requestID"]:
                        q_standard_num += requests[old_request_id][RequestInfoEnum.pallets.name][
                            PackageEnum.q_standard.name]
                        q_small_num += requests[old_request_id][RequestInfoEnum.pallets.name][PackageEnum.q_small.name]
                        q_box_num += requests[old_request_id][RequestInfoEnum.pallets.name][PackageEnum.q_box.name]
                        process_time += requests[old_request_id][RequestInfoEnum.process_time.name]
                        if Configs.constrains[ConstrainEnum.bin_packing]:
                            bin_dimension_list += requests[old_request_id][RequestInfoEnum.bin_dimension.name]
                        demand += requests[old_request_id][RequestInfoEnum.demand.name]
                    new_request[RequestInfoEnum.pallets.name][PackageEnum.q_standard.name] = q_standard_num
                    new_request[RequestInfoEnum.pallets.name][PackageEnum.q_small.name] = q_small_num
                    new_request[RequestInfoEnum.pallets.name][PackageEnum.q_box.name] = q_box_num

                    new_request[RequestInfoEnum.demand.name] = demand
                    assert request_batch[id][request_id]["volume"] == new_request[RequestInfoEnum.demand.name]
                    left_tw = str(request_batch[id][request_id]["min_creation_time"])
                    right_tw = str(request_batch[id][request_id]["max_tw_right"])
                    new_request[RequestInfoEnum.creation_time.name] = left_tw
                    new_request[RequestInfoEnum.pickup_timeWindow.name] = [left_tw, right_tw]
                    new_request[RequestInfoEnum.delivery_timeWindow.name] = [left_tw, right_tw]
                    new_request[RequestInfoEnum.process_time.name] = process_time
                    if Configs.constrains[ConstrainEnum.incompatible_items]:
                        new_request[RequestInfoEnum.incompatible_item_type_list.name] = request_batch[id][request_id][
                            RequestInfoEnum.incompatible_item_type_list.name]
                    if Configs.constrains[ConstrainEnum.bin_packing]:
                        new_request[RequestInfoEnum.bin_dimension.name] = bin_dimension_list
                    if Configs.constrains[ConstrainEnum.incompatible_items] or \
                            Configs.constrains[ConstrainEnum.incompatible_item_vehicle]:
                        new_request[RequestInfoEnum.item_type.name] = request_batch[id][request_id][RequestInfoEnum.item_type.name]

                    request_id = str(request_id)
                    new_requests[request_id] = new_request
        return new_requests, old_requests_map

    @staticmethod
    def old_requests_cluster(request_id_on_order: list, requests_items_map: dict, ongoing_items_map: dict,
                             vehicle_id: str):
        id = 1000
        new_request_id_on_order = []
        new_requests_items_map = {}
        n = len(request_id_on_order)
        left, rk = 0, 0

        while left < n:
            while rk + 1 < n and ongoing_items_map[
                requests_items_map[request_id_on_order[rk + 1]][DemandTypeEnum.delivery_only.name][0]][
                "delivery_factory_id"] \
                    == ongoing_items_map[
                requests_items_map[request_id_on_order[left]][DemandTypeEnum.delivery_only.name][0]][
                "delivery_factory_id"]:
                rk += 1
            new_id = str(id) + vehicle_id
            new_request_id_on_order.append(new_id)
            new_requests_items_map[new_id] = {DemandTypeEnum.delivery_only.name: []}
            for i in range(left, rk + 1):
                for item_id in requests_items_map[request_id_on_order[i]][DemandTypeEnum.delivery_only.name]:
                    new_requests_items_map[new_id][DemandTypeEnum.delivery_only.name].append(item_id)
            id += 1
            left = rk + 1
            rk += 1
        return new_request_id_on_order, new_requests_items_map


if __name__ == "__main__":
    pass
