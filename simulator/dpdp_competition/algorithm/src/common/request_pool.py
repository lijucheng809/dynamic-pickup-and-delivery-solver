from datetime import datetime, timedelta

from simulator.dpdp_competition.algorithm.src.enum.request_info_enum import RequestInfoEnum

class RequestPool(object):
    def __init__(self):
        """
        是否需要对requests按紧急程度进行排序？
        requests: dict
          key:     requestID
          value:   {"pickup_demand_info": pickupDemandInfo
                   "delivery_demand_info": deliveryDemandInfo，
                   ”creation_time“: time,
                   "finish_time": None}
        pickupCustomer = {"customerID": ID,
                          "customerPosition": position,
                          "demand": volume,
                          "time_window": timeWindow}
        """
        self.__unDispatchedRequestPool = dict()
        self.__dispatchedRequestPool = dict()
        self.__finishedRequestPool = dict()
        self.__request_id_bin_map = dict()
        self.__request_is_dimension_map = dict()

    def push_request_bin_map_2_request_pool(self, request_bin_map: dict):
        self.__request_id_bin_map = request_bin_map

    def updateUnDispatchRequest(self, requests: dict, index="add"):
        """
        :param requests:
        :param index: type: str, [add, dispatch]
        :return: None
        """
        if index == "add":
            for key, value in requests.items():
                self.__unDispatchedRequestPool[key] = value
        else:
            for key in requests:
                self.__unDispatchedRequestPool.pop(key)

    def updateDispatchedRequestPool(self,
                                    request_id: str,
                                    index: str,
                                    request_finish_time=datetime.now()):
        """
        :param request_id:
        :param index: type: str, [add, finish, remove]
        :param request_finish_time: type: datetime
        :return: None
        """
        if index == "add":
            self.__dispatchedRequestPool[request_id] = self.__unDispatchedRequestPool[request_id]
            self.__unDispatchedRequestPool.pop(request_id)
        elif index == "finish":
            self.__dispatchedRequestPool[request_id]["finishTime"] = request_finish_time
            self._updateFinishedRequestPool(request_id)
            self.__dispatchedRequestPool.pop(request_id)
        else:
            self.__dispatchedRequestPool.pop(request_id)

    def _updateFinishedRequestPool(self, request_id: str):
        """
        如果request完成，则将完成的request更新至finishedRequestPool中
        :param request_id: dict
        :return: None
        """
        self.__finishedRequestPool[request_id] = self.__dispatchedRequestPool[request_id]

    def emptyUnDispatchedPool(self):
        if not bool(self.__unDispatchedRequestPool):
            return True
        return False

    def gen_request_id_dimension_map(self):
        for request_id, request in self.__unDispatchedRequestPool.items():
            self.__request_is_dimension_map[request_id] = request[RequestInfoEnum.bin_dimension.name]

    @property
    def get_request_id_dimension_map(self):
        return self.__request_is_dimension_map

    @property
    def getUnDispatchedPool(self):
        return self.__unDispatchedRequestPool

    @property
    def getDispatchedPool(self):
        return self.__dispatchedRequestPool
