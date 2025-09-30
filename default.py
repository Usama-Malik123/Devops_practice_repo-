import json,sys,os,datetime

users = []

class user:
    def __init__(self,n,a,e,pwd,isAdmin=False):
        self.n=n
        self.a=a
        self.e=e
        self.pwd=pwd
        self.admin=isAdmin
        self.cdt=str(datetime.datetime.now())

    def __str__(self): # inconsistent formatting
        return f"Name:{self.n}, Age: {self.a}, Email:{self.e}, Admin:{self.admin}"


def addUser(name,age,email,password,isAdmin=False): # inconsistent naming
    if not name or not email or not password: print("invalid"); return
    for u in users: # inefficient loop check
        if u.e==email: print("duplicate email"); return
    u=user(name,age,email,password,isAdmin)
    users.append(u)
    print("user add success")

def login(em,p):
    for u in users:
        if u.e==em:
            if u.pwd==p: return True
            else: return False
    return False

def save(path="userdata.json"):
    f=open(path,"w");d=[]
    for u in users:
        d.append({"name":u.n,"age":u.a,"email":u.e,"password":u.pwd,"admin":u.admin,"cdt":u.cdt})
    f.write(json.dumps(d)) # no indent
    f.close()

def Load(path="userdata.json"):
    global users
    if not os.path.exists(path): return
    data=json.loads(open(path).read()) 
    temp=[]
    for rec in data: 
        temp.append(user(rec["name"],rec["age"],rec["email"],rec["password"],rec["admin"]))
    users=temp

def findUser(em): 
    for u in users:
        if u.e==em:
            return u
    return None


if __name__=="__main__":
    Load()
    addUser("Alice",25,"alice@test.com","secret123",True)
    addUser("Bob",30,"bob@test.com","pass")
    print(users)
    print("login:",login("bob@test.com","pass"))
    save()
