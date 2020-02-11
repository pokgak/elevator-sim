# schema.py

PERSON_SCHEMA = {
    "type": "object",
    "required": ["start_floor", "end_floor", "start_timestamp"],
    "properties": {
        "start_floor": {"type": "number"},
        "end_floor": {"type": "number"},
        "start_timestamp": {"type": "string"},
        "end_timestamp": {"type": "string"},
        "enter_elevator_timestamp": {"type": "string"},
        "leave_elevator_timestamp": {"type": "string"},
    },
}

ELEVATOR_MAX_CAPACITY = {
    "type": "object",
    "required": ["max", "actual"],
    "properties": {"max": {"type": "number"}, "actual": {"type": "number"}},
}

ELEVATOR_QUEUE = {"type": "array", "items": {"type": "number"}}

SIMULATION_PASSENGER_WAITING = {"type": "array", "items": PERSON_SCHEMA}

SIMULATION_PASSENGER_ARRIVED = {
    "type": "object",
    "properties": {
        "elevator": {"type": "number"},
        "list": {"type": "array", "items": PERSON_SCHEMA},
    },
}

# Example usage. Run with `python3 schema.py`.
if __name__ == "__main__":
    import jsonschema
    from data import Passenger

    test = {"elevator": 0, "list": [Passenger(1, 4).to_json()]}

    # returns nothing when valid
    jsonschema.validate(test, SIMULATION_PASSENGER_ARRIVED)

    # try:
    #     jsonschema.validate(test, SIMULATION_PASSENGER_ARRIVED)
    # except jsonschema.ValidationError as ve:
    #     print(ve)
    # except jsonschema.SchemaError as se:
    #     print(se)
