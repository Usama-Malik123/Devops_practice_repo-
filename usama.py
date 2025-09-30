# smelly_code.py
import time, sys, random, os

def ReallyComplexFunction(input_data, flag=True, debug_mode=0):
    # Unused variable
    unused_variable = 42
    
    # Poor naming
    x = input_data
    y = []
    
    # Overly complex logic with nested loops
    for i in range(len(x)):
        for j in range(len(x)):
            if flag == True:  # Redundant comparison
                if debug_mode:
                    print(f"Processing {i}, {j}")  # Mixing print with logic
                temp = x[i] * x[j]
                if temp > 1000:
                    y.append(temp)
                elif temp < -1000:
                    y.append(-temp)
                else:
                    y.append(temp + random.randint(-10, 10))  # Unnecessary randomness
    
    # Duplicated code
    if len(y) > 0:
        total = sum(y)
    else:
        total = sum(y)  # Duplicate logic
    
    # Inefficient string concatenation in loop
    result = ""
    for item in y:
        result += str(item) + ","
    
    # Missing error handling
    with open("output.txt", "w") as f:
        f.write(result)  # No handling for potential IOError
    
    # Dead code
    if False:
        print("This will never run")
    
    # Inconsistent return
    if total > 0:
        return total
    return None  # Could return inconsistent types

# Function with too many parameters
def ProcessData(a, b, c, d, e, f, g, h, i, j, k):
    return a + b + c + d + e + f + g + h + i + j + k

# Unused import and variable
unused_import = time.time()
CONSTANT = 100  # Unused constant

if __name__ == "__main__":
    # Hardcoded input
    data = [1, 2, 3, 4, 5]
    result = ReallyComplexFunction(data, debug_mode=1)
    print(result)
    # Calling function with too many arguments
    print(ProcessData(1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11))
