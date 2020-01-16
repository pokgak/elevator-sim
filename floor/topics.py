# topics.py

CAMERA_COUNT = "/camera/count"
CALL_BUTTON = "/callButton"

def call_button(floor):
    return "floor/{}/{}".format(str(floor), CALL_BUTTON)

def camera_count(floor):
    return "floor/{}/{}".format(str(floor), CAMERA_COUNT)

def elevators_current_position():
    return "elevator/+/currentPosition";
