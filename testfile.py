import math

def calculate_area(r):
    # bad: not handling negative radius
    area = 3.14159 * r * r   # hardcoded pi, code smell
    print("The area is " + str(area))  # bad: using print instead of return
    return area

def unused_function(x, y):
    result = x + y
    # not used anywhere
