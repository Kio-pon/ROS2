# DICTIONARIES

# lst = [1,2,3,3,4,5,6]

# # lst [ 0 ]   =>  1
#     # key   =>  value


# # A dictionary stores data as key-value pairs.
# # Instead of using a position like a list, you use a key to get a value.

# data = {"Email#1" : "azyan@gmail.com" , "Email#2" : "ahmed@gmail.com"}
#     #     Key     =>      Value

# print(data["Email#2"])

# dicto = { "Name" : "Azyan" , "GPA" : 3.8 , "Email" : "azy@gmial.com"  }

# lst = [ "Azyan "  , 3.8, "Azy@gmail.com" ]

# LST[1]

# print(dicto["Email"])

# print(lst[0])

# print(data["Email"])
# lst = [123]
# tup = (123,)


student = {"name": "Ali", "age": 20, "grade": 85}

# print(student)


# print(student["name"])
# print(student["grade"])

# Trying to access a key that does not exist gives an error.
# print(student["email"])


# ADDING AND UPDATING``


# print(Azyan)

# Azyan[ "InstaID" ] = "azyan._.ahmed"



# print(Azyan)

# Azyan["grade"] = 60   # updates an existing value
# print(Azyan)


# # REMOVING

# del Azyan["grade"]
# print(Azyan)

# removed_value = Azyan.pop("age")
# print(removed_value)
# print(Azyan)


# CHECKING AND INSPECTING


# print("name" in Azyan)

# print("InstaID" in Azyan)

# print(len(student))


# print(list(Azyan.keys()))

Azyan = {"name": "Azyan", "age": 19, "grade": 95}

# print(Azyan.values())

# print(list(Azyan.values()))

# print(Azyan.items())


# # LOOPING OVER A DICTIONARY

# # looping gives you the keys by default
# # for key in student:
# #     print(key)

# # looping over values
# # for value in student.values():
# #     print(value)

# # looping over both at once
# # for key, value in Azyan.items():
# #     print(key, ":", value)


# # NESTED DICTIONARIES

# # a dictionary can hold another dictionary as a value

# NESTEDlist = [  [1,2,3] ,
#                 [2,3,4],
#                 [3,4,5]]

# # print ( NESTEDlist[1][2])



# print(students["student2"]["name"])

# print(students["student2"])
# print(students["student2"]["name"])
# print(students["student2"]["grade"])


# looping through a nested dictionary
student1 = {"Name" : "Azyan", "grade" : 95}
student2 = {"Name" : "Ahmed", "grade" : 90}


studentData = { "Student1" : {"Name" : "Azyan", "Age":19, "grade":95}, 
                "Student2" : {"Name" :"Maaz", "Age":19, "grade":90 },
                "Student3" : {"Name" :"Hamzah", "Age":20, "grade":95 }}


print(student1["grade"])

print(studentData["Student1"]["grade"])





# for key, value in students.items(): # key , value
#     print(key)
#     # print(value["name"])
    # print(value["grade"])


# updating a value inside a nested dictionary

# students["student1"]["grade"] = 90
# print(students["student1"])








# Create a dictionary called me with these keys: name, age, favorite_food, and superpower.

# Fill in the dictionary with your own answers, but for superpower, make one up. Anything goes, like "never gets hungry" 
# or "can nap anywhere".

# Print your profile like this, using the actual keys, not by typing the words again:

# Name: Ali
# Age: 20
# Favorite Food: Biryani
# Superpower: never gets hungry

# Add a new key called catchphrase with something funny you'd say if you had that superpower.

# Check if "villain_name" is a key in your dictionary, and print the result. Spoiler, 
# it shouldn't be there yet.

# Add "villain_name" as a key, give yourself a ridiculous villain name as the value, 
# then print the whole dictionary using .items().



# me = {"name":"Maaz","age":12,"favorite_food":"Pulao","superpower":"Never gets tired"}
# print("name:",me["name"])
# print("age:",me["age"])
# print("favorite food:",me["favorite_food"])
# print("superpower:",me["superpower"])
# me["catchphrase"]= "i am him"
# print("villan_name" in me)
# me["villan_name"]= "voldermort ki chatti copy"
# for key, value in me.items():
#     print(key," = ",value)



# You're given a dictionary of animals in a zoo. Each animal has its own dictionary of details.
pythonzoo = {
    "Leo": {"animal": "lion", "age": 5, "favorite_snack": "raw meat"},
    "Dumbo": {"animal": "elephant", "age": 12, "favorite_snack": "peanuts"},
    "Spike": {"animal": "porcupine", "age": 3, "favorite_snack": "berries"}
}

# Print Leo's favorite snack using two levels of indexing.
# Add a new key called sound to each animal's dictionary, with a sound of your choice, like "roar" for Leo.
# Loop through zoo using .items() and print each animal like this:

# Leo the lion says roar and loves raw meat

# Add a brand new animal to the zoo. Give it a name, an animal type, an age, a favorite snack, and a sound.
# Loop through zoo again, but this time only print the animals that are older than 4 years.
# Pick your favorite animal in the zoo and give it a "best_friend" key,
#  with the name of another animal in the zoo as the value.


for key , value in pythonzoo.items():
    print(f"{key} the {value["animal"]} is {value["age"]} years old and loves {value["favorite_snack"]}")