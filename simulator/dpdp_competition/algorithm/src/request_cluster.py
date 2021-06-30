from datetime import datetime, timedelta
from simulator.dpdp_competition.algorithm.conf.configs import configs


def cluster(requests):
    request_batch = {}
    new_requests = {}
    new_request_id = 100
    for requestID in requests:
        p_id = requests[requestID]["pickup_customer_id"]
        d_id = requests[requestID]["delivery_customer_id"]
        id = p_id + d_id
        tw_right = datetime.strptime(requests[requestID]["pickup_timeWindow"][1], "%Y-%m-%d %H:%M:%S")
        creation_time = datetime.strptime(requests[requestID]["creation_time"], "%Y-%m-%d %H:%M:%S")
        volume = requests[requestID]["demand"]
        if id not in request_batch:
            request_batch[id] = {}
        if not request_batch[id]:
            request_batch[id] = {new_request_id: {"old_requestID": [requestID],
                                                  "min_creation_time": creation_time,
                                                  "max_creation_time": creation_time,
                                                  "volume": volume,
                                                  "max_tw_right": tw_right,
                                                  "min_tw_right": tw_right}}
            new_request_id += 1
        else:
            flag = True
            for request_id in request_batch[id]:
                min_creation_time = min(creation_time, request_batch[id][request_id]["min_creation_time"])
                max_creation_time = max(creation_time, request_batch[id][request_id]["max_creation_time"])
                min_tw_right = min(tw_right, request_batch[id][request_id]["min_tw_right"])
                max_tw_right = max(tw_right, request_batch[id][request_id]["max_tw_right"])
                if volume + request_batch[id][request_id]["volume"] <= configs.vehicle_capacity and \
                        min_creation_time + timedelta(minutes=90) >= max_creation_time:
                    flag = False
                    request_batch[id][request_id]["old_requestID"].append(requestID)
                    request_batch[id][request_id]["volume"] += volume
                    request_batch[id][request_id]["min_creation_time"] = min_creation_time
                    request_batch[id][request_id]["max_creation_time"] = max_creation_time
                    request_batch[id][request_id]["min_tw_right"] = min_tw_right
                    request_batch[id][request_id]["max_tw_right"] = max_tw_right
                    break
            if flag:
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
                sample_request = requests[old_request_id_1]
                q_standard_num, q_small_num, q_box_num, process_time = 0, 0, 0, 0
                for old_request_id in request_batch[id][request_id]["old_requestID"]:
                    q_standard_num += requests[old_request_id]["pallets"]["q_standard"]
                    q_small_num += requests[old_request_id]["pallets"]["q_small"]
                    q_box_num += requests[old_request_id]["pallets"]["q_box"]
                    process_time += requests[old_request_id]["load/unload_time"]
                sample_request["pallets"]["q_standard"] = q_standard_num
                sample_request["pallets"]["q_small"] = q_small_num
                sample_request["pallets"]["q_box"] = q_box_num
                sample_request["demand"] = q_standard_num + q_small_num + q_box_num
                assert request_batch[id][request_id]["volume"] == sample_request["demand"]
                left_tw = str(request_batch[id][request_id]["max_creation_time"])
                right_tw = str(request_batch[id][request_id]["max_tw_right"])
                sample_request["pickup_timeWindow"] = [left_tw, right_tw]
                sample_request["delivery_timeWindow"] = [left_tw, right_tw]
                sample_request["load/unload_time"] = process_time
                request_id = str(request_id)
                new_requests[request_id] = sample_request
    return new_requests, old_requests_map


def ongoing_request_cluster(request_id_on_order: list, requests_items_map: dict, ongoing_items_map: dict,
                            vehicle_id: str):
    id = 1000
    new_request_id_on_order = []
    new_requests_items_map = {}
    n = len(request_id_on_order)
    left, rk = 0, 0

    while left < n:
        while rk + 1 < n and ongoing_items_map[requests_items_map[request_id_on_order[rk + 1]]["delivery_only"][0]][
            "delivery_factory_id"] \
                == ongoing_items_map[requests_items_map[request_id_on_order[left]]["delivery_only"][0]]["delivery_factory_id"]:
            rk += 1
        new_id = str(id) + vehicle_id
        new_request_id_on_order.append(new_id)
        new_requests_items_map[new_id] = {"delivery_only": []}
        for i in range(left, rk+1):
            for item_id in requests_items_map[request_id_on_order[i]]["delivery_only"]:
                new_requests_items_map[new_id]["delivery_only"].append(item_id)
        id += 1
        left = rk + 1
        rk += 1
    return new_request_id_on_order, new_requests_items_map
