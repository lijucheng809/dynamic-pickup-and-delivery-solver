import json
import os
import time
from datetime import datetime

from simulator.dpdp_competition.algorithm.conf.configs import Configs
from simulator.dpdp_competition.algorithm.data_transfomer.data_transfomer import DataTransformer
from simulator.dpdp_competition.algorithm.src.enum.request_info_enum import RequestInfoEnum


class SimOutputConverter(object):
    def __init__(self):
        # self.__middle_vehicle_info = None
        with open(Configs.customer_info_path, "r") as f:
            self.__customer_id_info_map = json.load(f)
        with open(Configs.vehicle_info_path, "r") as f:
            self.__vehicles_info = json.load(f)
        with open(Configs.ongoing_items_path, "r") as f:
            self.__ongoing_items = json.load(f)
        # if os.path.exists(Configs.middle_vehicle_info_path):
        #     with open(Configs.middle_vehicle_info_path, "r") as f:
        #         self.__middle_vehicle_info = json.load(f)
        self.__time_out_requests = {}
        if os.path.exists(Configs.time_out_requests):
            with open(Configs.time_out_requests, "r") as f:
                self.__time_out_requests = json.load(f)
        self.__ongoing_items_map = {}
        for item in self.__ongoing_items:
            self.__ongoing_items_map[item["id"]] = item
        self.__vehicles_info_map = {}
        for vehicle_info in self.__vehicles_info:
            self.__vehicles_info_map[vehicle_info["id"]] = vehicle_info
        self.__request_info = DataTransformer.requests_sim_2_algo()
        for requestID in self.__request_info["requests"]:
            if requestID in self.__time_out_requests:
                self.__request_info["requests"][requestID][RequestInfoEnum.pickup_timeWindow.name][1] = \
                    self.__time_out_requests[requestID]["pickup_demand_info"]["time_window"][1]
                self.__request_info["requests"][requestID][RequestInfoEnum.delivery_timeWindow.name][1] = \
                    self.__time_out_requests[requestID]["delivery_demand_info"]["time_window"][1]
            else:
                if "-" in requestID:
                    index_ = requestID.index("-")
                    order_id_new = requestID[:index_]
                    if order_id_new in self.__time_out_requests:
                        self.__request_info["requests"][requestID][RequestInfoEnum.pickup_timeWindow.name][1] = \
                            self.__time_out_requests[order_id_new]["pickup_demand_info"]["time_window"][1]
                        self.__request_info["requests"][requestID][RequestInfoEnum.delivery_timeWindow.name][1] = \
                            self.__time_out_requests[order_id_new]["delivery_demand_info"]["time_window"][1]

        self.__next_period_vehicle_go_time = None
        for vehicle_info in self.__vehicles_info:
            update_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(vehicle_info["update_time"]))
            time_2_go = datetime.strptime(update_time, "%Y-%m-%d %H:%M:%S")
            if not self.__next_period_vehicle_go_time:
                self.__next_period_vehicle_go_time = time_2_go
                break

    @property
    def get_request_info(self):
        return self.__request_info

    @property
    def get_customer_id_info_map(self):
        return self.__customer_id_info_map

    @property
    def get_vehicles_info(self):
        return self.__vehicles_info

    @property
    def get_ongoing_items_map(self):
        return self.__ongoing_items_map

    # @property
    # def get_middle_vehicle_info(self):
    #     return self.__middle_vehicle_info

    @property
    def get_vehicles_info_map(self):
        return self.__vehicles_info_map

    @property
    def get_go_time(self):
        return self.__next_period_vehicle_go_time
