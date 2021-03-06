from datetime import datetime, timedelta


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
        self._unDispatchedRequestPool = dict()
        self._dispatchedRequestPool = dict()
        self._finishedRequestPool = dict()

    def updateUnDispatchRequest(self, requests: dict, index="add"):
        """
        :param requests:
        :param index: type: str, [add, dispatch]
        :return: None
        """
        if index == "add":
            for key, value in requests.items():
                self._unDispatchedRequestPool[key] = value
        else:
            for key in requests:
                self._unDispatchedRequestPool.pop(key)

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
            self._dispatchedRequestPool[request_id] = self._unDispatchedRequestPool[request_id]
            self._unDispatchedRequestPool.pop(request_id)
        elif index == "finish":
            self._dispatchedRequestPool[request_id]["finishTime"] = request_finish_time
            self._updateFinishedRequestPool(request_id)
            self._dispatchedRequestPool.pop(request_id)
        else:
            self._dispatchedRequestPool.pop(request_id)

    def _updateFinishedRequestPool(self, request_id: str):
        """
        如果request完成，则将完成的request更新至finishedRequestPool中
        :param request_id: dict
        :return: None
        """
        self._finishedRequestPool[request_id] = self._dispatchedRequestPool[request_id]

    def emptyUnDispatchedPool(self):
        if not bool(self._unDispatchedRequestPool):
            return True
        return False

    @property
    def getUnDispatchedPool(self):
        return self._unDispatchedRequestPool

    @property
    def getDispatchedPool(self):
        return self._dispatchedRequestPool
