# # lst = [ 10 , 2 , 3 ,4 ,5]
# # lst1 = ["a" , "b", "c", "d"]

# # # print(lst1)
# # # # a b c d

# # # print("ind = " , lst1[0] , lst1[1] , lst1[2] , lst1[3] )

# # # string = "-TT-".join(lst1) 
# # # lst2 = [1, "s", 'd']
# # # print(string)

# # # # print all values of lst usinng index

# # # stri = " ".join(lst1[0:4])

# # # append -> lst.append(5) # lst = [ 10 , 2,3,4,5 , 5]
# # # insert -> lst.insert(2 , 10) # lst = [ 10 , 2,3,10, 4,5 , 5]
# # # pop -> lst.pop(2) # lst = [ 10 , 2,10, 4,5 ]
# # # remove -> lst.remove(10)  # lst = [ 2,10, 4,5 ]
# # # del -> del lst # 


# # # lst[-1] -> 5 


# # # print(lst)
# # # lst.insert( 2  , "a")
# # # print(lst)
# # lst = [ 10 , 2 , 3 ,4 ,5]

# # # print(len(lst))

# # # if 6 in lst:
# # #     print("ok")
# # # else:
# # #     print("not")

# # # lst = [ 10 , 2 , 3 ,4 ,5 ,5]

# # # print( lst.index(10) )

# # # print(lst.count(10))

# # # lst = [ 10 , 2 , 3 ,4 ,5 ,5]
# # # same var -> lst.sort()
# # # new var -> sorted(lst)

# # # lst1 = sorted(lst , reverse= True)

# # # print(lst)
# # # print(lst1)

# # # list grades - >  85, 92, 78, 95, 88, 78, 60

# # # print first grade and last grade using index

# # # print first 3 grades indexes 

# # # add a new grade at the end 74 

# # # insert a new grade at idnex2 100
# # # remove first 78 walay grade ko 

# # # pop index4 kay grade ko

# # # index 1 kay grade ko change karba with 100 

# # # total grades print karne hay as in the umber for elements 

# # # then cehck 95 if in list then print the list

# # # find the index of 88
# # # count no of 77s in the list 

# # # sort the list in sam variable 

# # # print a new variable with reverse sort 


# # lst = [ 10 , 2 , 3 ,4 ,5]

# # # for i in range(1 , len(lst) , 2):
# # #     print( lst [i] )
# #     # val = lst[i]
# # # index 


# # # for val in lst:
# # #     print(val)
# # #     ind = lst.index(val)
# # #     if ind %2 == 0:

# # # # direct val 4


# # # for ind , val in enumerate(lst):
# # #     if ind %2 ==0:
# # #         print(val*2)


# # # num = 1

# # # lst = [ 0 , 1 , 2 , 3]
# print()
# print()
# print()

# # # nested = [ ["football" , "ghomne"] ,["sleep"] , ["running"]]

# # # for val in nested:
# # #     print(" ".join(val))

# # Nested Lists
# # nested = [ ["Ali", 85] , ["Sara", 92] , ["Omar", 78]  ]

# # nested [0] .pop(1)
# # nested[0].append(96)
# # nested.append(["Hassan", 100])
# # nested.insert(4 , "End")
# # print(nested)

# # Matrix = [[1,2,3] , [4,5,6] , [7,8,9]]
# # print(Matrix)

# # # Matrix.pop(0)
# # for  row in Matrix: 
# #     print("orig Row  " , row)
# #     row.pop(0)
# #     row.pop(0)
# #     print("mod row" , row)
# # print(Matrix)
# #               0            1            2 
# #              0  1  
# # print(nested)
# # print(nested[0][0]) 
# # aliList = nested[0]
# # # print(aliList)
# # # print(aliList[0])


# # # nested =  [ [1, 2, 3, 4],
# # #             [5, 6, 7, 8],
# # #             [9, 10, 11, 12] ]
# # # #  0   1   2

# # #  "Ali   
# # # # -inf -1 0 1 inf

# # aliList[1] = str(aliList[1])
# # print(" - ".join(aliList))


# scores = [[80, 90, 70],[80, 90, 70], [60, 75, 85], [95, 100, 90], [50, 65, 70]]


# # 1st ->  0 
# # 2nd ->  1
# # 3rd ->  2

# # print second test score of 1st student 
# # ``

# # change third score of last student to 100

# scores[-1][2] = 100 


# # OR 
# scores[-1].pop(2)
# scores[-1].insert(2, 100)
# # print(scores)

# # loop through scores with a single for loop and print each students full list of score 
# #  like this 
# #  [80, 90, 70]
# #  [60, 75, 85]
# #  [95, 100, 90]
# #  [50, 65, 70]

# # loop through scores using two nested for loop and print indicidual scores
# #  like this 
# # student 1 : 80
# # student 1 : 90
# # student 1 : 70
# # student 2 : 60
# # student 2 : 75
# # student 2 : 85
# # student 3 : 95
# # student 3 : 100
# # student 3 : 90
# # student 4 : 50
# # student 4 : 65
# # student 4 : 70


# # add up all scores of each student using nested loop and print each students totalt 
# # like this 
# # student 1 : 240 
# # student 2 : 225 
# # student 3 : 285 
# # student 4 : 185


# # find and print the higest score in the entire grid using nested loop
# # like this
# # highest score :
# # student 4 : 100 

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
