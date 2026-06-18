# lst = [ 10 , 2 , 3 ,4 ,5]
# lst1 = ["a" , "b", "c", "d"]

# # print(lst1)
# # # a b c d

# # print("ind = " , lst1[0] , lst1[1] , lst1[2] , lst1[3] )

# # string = "-TT-".join(lst1) 
# # lst2 = [1, "s", 'd']
# # print(string)

# # # print all values of lst usinng index

# # stri = " ".join(lst1[0:4])

# # append -> lst.append(5) # lst = [ 10 , 2,3,4,5 , 5]
# # insert -> lst.insert(2 , 10) # lst = [ 10 , 2,3,10, 4,5 , 5]
# # pop -> lst.pop(2) # lst = [ 10 , 2,10, 4,5 ]
# # remove -> lst.remove(10)  # lst = [ 2,10, 4,5 ]
# # del -> del lst # 


# # lst[-1] -> 5 


# # print(lst)
# # lst.insert( 2  , "a")
# # print(lst)
# lst = [ 10 , 2 , 3 ,4 ,5]

# # print(len(lst))

# # if 6 in lst:
# #     print("ok")
# # else:
# #     print("not")

# # lst = [ 10 , 2 , 3 ,4 ,5 ,5]

# # print( lst.index(10) )

# # print(lst.count(10))

# # lst = [ 10 , 2 , 3 ,4 ,5 ,5]
# # same var -> lst.sort()
# # new var -> sorted(lst)

# # lst1 = sorted(lst , reverse= True)

# # print(lst)
# # print(lst1)

# # list grades - >  85, 92, 78, 95, 88, 78, 60

# # print first grade and last grade using index

# # print first 3 grades indexes 

# # add a new grade at the end 74 

# # insert a new grade at idnex2 100
# # remove first 78 walay grade ko 

# # pop index4 kay grade ko

# # index 1 kay grade ko change karba with 100 

# # total grades print karne hay as in the umber for elements 

# # then cehck 95 if in list then print the list

# # find the index of 88
# # count no of 77s in the list 

# # sort the list in sam variable 

# # print a new variable with reverse sort 


# lst = [ 10 , 2 , 3 ,4 ,5]

# # for i in range(1 , len(lst) , 2):
# #     print( lst [i] )
#     # val = lst[i]
# # index 


# # for val in lst:
# #     print(val)
# #     ind = lst.index(val)
# #     if ind %2 == 0:

# # # direct val 4


# # for ind , val in enumerate(lst):
# #     if ind %2 ==0:
# #         print(val*2)


# # num = 1

# # lst = [ 0 , 1 , 2 , 3]
print()
print()
print()

# # nested = [ ["football" , "ghomne"] ,["sleep"] , ["running"]]

# # for val in nested:
# #     print(" ".join(val))

# Nested Lists
# nested = [ ["Ali", 85] , ["Sara", 92] , ["Omar", 78]  ]

# nested [0] .pop(1)
# nested[0].append(96)
# nested.append(["Hassan", 100])
# nested.insert(4 , "End")
# print(nested)

# Matrix = [[1,2,3] , [4,5,6] , [7,8,9]]
# print(Matrix)

# # Matrix.pop(0)
# for  row in Matrix: 
#     print("orig Row  " , row)
#     row.pop(0)
#     row.pop(0)
#     print("mod row" , row)
# print(Matrix)
#               0            1            2 
#              0  1  
# print(nested)
# print(nested[0][0]) 
# aliList = nested[0]
# # print(aliList)
# # print(aliList[0])


# # nested =  [ [1, 2, 3, 4],
# #             [5, 6, 7, 8],
# #             [9, 10, 11, 12] ]
# # #  0   1   2

# #  "Ali   
# # # -inf -1 0 1 inf

# aliList[1] = str(aliList[1])
# print(" - ".join(aliList))


scores = [[80, 90, 70],[80, 90, 70], [60, 75, 85], [95, 100, 90], [50, 65, 70]]


# 1st ->  0 
# 2nd ->  1
# 3rd ->  2

# print second test score of 1st student 
# ``

# change third score of last student to 100

scores[-1][2] = 100 


# OR 
scores[-1].pop(2)
scores[-1].insert(2, 100)
# print(scores)

# loop through scores with a single for loop and print each students full list of score 
#  like this 
#  [80, 90, 70]
#  [60, 75, 85]
#  [95, 100, 90]
#  [50, 65, 70]

# loop through scores using two nested for loop and print indicidual scores
#  like this 
# student 1 : 80
# student 1 : 90
# student 1 : 70
# student 2 : 60
# student 2 : 75
# student 2 : 85
# student 3 : 95
# student 3 : 100
# student 3 : 90
# student 4 : 50
# student 4 : 65
# student 4 : 70


# add up all scores of each student using nested loop and print each students totalt 
# like this 
# student 1 : 240 
# student 2 : 225 
# student 3 : 285 
# student 4 : 185


# find and print the higest score in the entire grid using nested loop
# like this
# highest score :
# student 4 : 100 




print()
print()
print()