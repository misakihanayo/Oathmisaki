import time,threading
import socket
import random
import queue

def datapack_generation(name,queryid,number):
    hexqueryid='%s'%(chr(queryid))
    hexnum='%s'%(chr(number))
    hoststr=''
    for x in name.split('.'):
        hoststr=hoststr+chr(len(x))+x
    data='%s%s\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00%s\x00\x00\x01\x00\x01' % (hexqueryid,hexnum,hoststr)
    return data

class Locallist(object):
    def __init__(self):
        self.dic={} #ip-DNS table local cache
        self.buffer={} #Host request cache
        self.sendtime={}
        self.sem=1 #lock of sendtime
        self.Localserver='202.38.93.153'
        self.Client='127.0.0.1'
        self.Port=53
        self.MaxWaitingTime=2
        self.input=queue.Queue() #DNS request
        self.output=queue.Queue() #DNS return
        self.sockin=socket.socket(socket.AF_INET,socket.SOCK_DGRAM) #socket to client
        self.sockin.bind((self.Client,self.Port))
        self.sockout=socket.socket(socket.AF_INET,socket.SOCK_DGRAM) #socket to server

    def GetSem(self):
        if (self.sem==1):
            self.sem=0
            return 1
        else:
            return 0
    
    def ReturnSem(self):
        if (self.sem==0):
            self.sem=1
        else:
            print('Error: Sem')

    def Read_Config(self): #local DNS list
        config_file=open('config.txt','r')
        for line in config_file.readlines():
            self.dic[(line.strip()).split(' ',1)[1]]=(line.strip()).split(' ',1)[0]
        print(self.dic)
        config_file.close()

    def ExternQuery(self,name,queryid,number):
        data=datapack_generation(name,queryid,number)
        print('External Query')
        self.sockout.sendto(bytes(data, encoding="iso8859"),(self.Localserver,53))
        msg=self.sockout.recvfrom(1024)
        self.output.put(msg)

    def timer(self,name,queryid,number,t0):
        t1=time.time()
        str_queryid=str(queryid)
        while (str_queryid in self.sendtime and (t1-t0)<self.MaxWaitingTime):
            t1=time.time()
        while (self.GetSem()==0):
            pass
        if (str_queryid in self.sendtime):
            if (number<4):
                self.sendtime[str_queryid]=(number+1,time.time())
                print("Timeout:",number)
                threading.Thread(target=self.timer,args=(name,queryid,number+1,(self.sendtime[str_queryid])[1],)).start()
                threading.Thread(target=self.ExternQuery,args=(name,queryid,number+1)).start()
            else:
                self.buffer.pop(str_queryid)
                self.sendtime.pop(str_queryid)
                print("Timeout 3 times, request aborted")
            self.ReturnSem()
        else:
            print('accepted')
            self.ReturnSem()

    def SendBack(self,msg,ip,addr):
        strmsg=msg.decode(encoding='iso8859')
        length=len(strmsg)
        s1=strmsg[0:2]
        s2=strmsg[8:length]
        i=0
        ip4=['','','','']
        for x in ip.split('.'):
            ip4[i]=chr(int(x))
            i=i+1
        if (ip=='0.0.0.0'):
            data='%s\x81\x83\x00\x01\x00\x00%s\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\xdd\x00\x04%s%s%s%s'%(s1,s2,ip4[0],ip4[1],ip4[2],ip4[3])
        else:
            data='%s\x81\x80\x00\x01\x00\x01%s\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\xdd\x00\x04%s%s%s%s'%(s1,s2,ip4[0],ip4[1],ip4[2],ip4[3])
        b_data=bytes(data, encoding = "iso8859")
        self.sockin.sendto(b_data,addr)
    
    def ReceivePackin(self):
        while(1):
            try:
                msg=self.sockin.recvfrom(1024)
                print('Received Pack.')
                self.input.put(msg)
            except:
                pass

    def LocalQuery(self,name):
        if name in self.dic :
            return (1,self.dic[name])
        else:
            return (0,'')

    def PackProcess_Local(self): #read query from queue
        while (1):
            if not self.input.empty():
                curpack=self.input.get()
                msgtype=curpack[0]
                addr=curpack[1]
                if not(msgtype[3]==131) and msgtype[5]==1 and msgtype[7]==0 :
                    queryid=chr(msgtype[0])+chr(msgtype[1])
                    queryname=''
                    i=12
                    while (msgtype[i]!=0):
                        i2=i+1+msgtype[i]
                        queryname=queryname+msgtype[i+1:i2].decode(encoding='iso8859')+'.'
                        i=i2
                    queryname=queryname[0:len(queryname)-1]
                    print('current query is')
                    print(queryname)
                    localquery=self.LocalQuery(queryname)
                    if (localquery[0]==1):
                        threading.Thread(target=self.SendBack, args=(msgtype,localquery[1],addr,)).start()
                    else:
                        while (self.GetSem()==0):
                            pass
                        queryid=random.randint(0,99)
                        while (str(queryid) in self.buffer):
                            queryid=random.randint(0,99)
                        str_queryid=str(queryid)
                        self.buffer[str_queryid]=(curpack,addr)
                        self.sendtime[str_queryid]=(1,time.time())
                        self.ReturnSem()
                        threading.Thread(target=self.timer,args=(queryname,queryid,2,(self.sendtime[str_queryid])[1],)).start()
                        threading.Thread(target=self.ExternQuery,args=(queryname,queryid,1,)).start()
    def PackProcess_Out(self):
        while(1):
            if (not self.output.empty()):
                curpack=self.output.get()
                curmsg=curpack[0]
                if (curmsg[7]>=1):
                    a_id=curmsg[0]
                    a_number=curmsg[1]
                    str_a_id=str(a_id)
                    while (self.GetSem()==0):
                        pass
                    if (not(curmsg[3]==131)):
                        if ((str_a_id in self.sendtime) and (self.sendtime[str_a_id])[0]==a_number):
                            ip=str(curmsg[-4])+'.'+str(curmsg[-3])+'.'+str(curmsg[-2])+'.'+str(curmsg[-1])
                            r_name=''
                            i=12
                            while(curmsg[i]!=0):
                                i2=i+1+curmsg[i]
                                r_name=r_name+curmsg[i+1:i2].decode(encoding='iso8859')+'.'
                                i=i2
                            r_name=r_name[0:len(r_name)-1]
                            self.dic[r_name]=ip
                            print("r_name is, ",r_name)
                            back=self.buffer[str_a_id]
                            back_id=str(back[0])
                            back_addr=back[1]
                            msgback=back_id+curmsg[2:].decode(encoding='iso8859')
                            b_msgback=bytes(msgback, encoding = "iso8859")
                            self.sockin.sendto(b_msgback,back_addr)
                            self.buffer.pop(str_a_id)
                            self.sendtime.pop(str_a_id)
                            print('ANSWER:',r_name)
                            print('ID:',repr(bytes(back_id, encoding = "iso8859")),'--->',str_a_id)
                    else:
                        if((str_a_id in self.sendtime) and (self.sendtime[str_a_id])[0]==a_number):
                            back=self.buffer[str_a_id]
                            back_id=back[0]
                            back_addr=back[1]
                            msgback=back_id+curmsg[2:].decode(encoding='iso8859')
                            b_msgback=bytes(msgback, encoding = "iso8859") 
                            self.sockin.sendto(b_msgback,back_addr)
                            self.buffer.pop(str_a_id)
                            self.sendtime.pop(str_a_id)
                    self.ReturnSem()

Local=Locallist()
Local.Read_Config()
threading.Thread(target=Local.ReceivePackin).start()
threading.Thread(target=Local.PackProcess_Local).start()
threading.Thread(target=Local.PackProcess_Out).start()

                            



