

class CustomerRequestCombination(object):
    def __init__(self,
                 customerID,
                 requestID,
                 demandType,
                 brother_customerID,
                 volume,
                 time_window,
                 processTime,
                 vehicleID):
        self.customerID = customerID
        self.requestID = requestID
        self.demandType = demandType
        self.volume = volume
        self.brother_customerID = brother_customerID
        self.timeWindow = time_window
        self.processTime = processTime
        self.vehicleID = vehicleID
        self.vehicleArriveTime = None
        self.startProcessTime = None
        self.vehicleDepartureTime = None
        self.vehicleArriveTime_normal = None
        self.volume_normal = None
        self.leftNode = None
        self.rightNode = None
        self.brotherNode = None

    def __lt__(self, other):
        return self.vehicleArriveTime < other.vehicleArriveTime

    def setNormalVolume(self, volume: float):
        self.volume_normal = volume

    def setNormalArriveTime(self, time: float):
        self.vehicleArriveTime_normal = time

    def setVehicleArriveTime(self, time):
        self.vehicleArriveTime = time

    def setVehicleDepartureTime(self, time):
        self.vehicleDepartureTime = time

    def setLeftNode(self, left_node):
        self.leftNode = left_node

    def setRightNode(self, right_node):
        self.rightNode = right_node

    def setBrotherNode(self, node):
        self.brotherNode = node

    def setStartProcessTime(self, time):
        self.startProcessTime = time
