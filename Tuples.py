
# TUPLES 

# lst =  [1,2,3,4,5]
# lst[3] = 18
# print(lst)

tup =  (1,2,3,4,5)
# tup[3] = 18

# tup = list(tup) # change to list
# tup[3] = 18 # change value
# tup = tuple(tup) # change back to tuple
# print(tup)
# 
tup = tup[:3] + (18,) + tup[4:] 
# tup = (1,2,3) + (18,) + (5,) = (1,2,3,18,5)
# tup = (1,2,3,18,5)
# print(tup)

# lstoneitem = [1]
# tuponetime = (1,)
# print(lstoneitem)
# print(tuponetime)
# print(type(lstoneitem))
# print(type(tuponetime))


# in isze index loops 

# tup = (1,2,3,4,5,6,7,8,9,10)   

# print(len(tup))
# print(tup[0:3])
# print(tup[3:5])
# print(tup[5:7])
# print(tup[7:9])
# print(tup[9:10])

# for i in range(len(tup)//2):
#     print(tup[i] , tup[i+len(tup)//2])
    


# userdata = ( "azyanahmed1@gmail.com" , "Qwerty@123")
# email , password = userdata
# # email = userdata[0]
# # password = userdata[1]

# print("Email: " , email)
# print("Password: " , password)

## HW : Tuples 

# Create a tuple called colors with five color names of your choice.
# Print the second and fourth color using indexing.
# Print the first three colors using slicing.
# Try changing the first color directly with colors[0] = "black". Run it, read the error, and write one line explaining why it happened.
# Fix the color at index 0 using the slicing method shown in class, the one that rebuilds the tuple in pieces. Change it to "black" and print the result.
# Create a one-item tuple called single holding the number 7. Print it and print its type to confirm it's a tuple and not just a number in brackets.
# Create a tuple called numbers with the values (10, 20, 30, 40, 50, 60). Use a for loop and len() to print each number alongside the number exactly halfway across the tuple from it, the way we did in class with the pairs.
# Create a tuple called student with three values: name, age, and grade. Unpack it into three variables in one line, then print each variable with a label, like "Name: Ali".
# Write a tuple called login with an email and a password. Unpack it into user_email and user_password, then print both.
