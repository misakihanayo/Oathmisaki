import time, threading
import socket
import random
import queue

def pack_data_q(name,queryid,number):
    hexqueryid='%s'%(chr(queryid))
    hexnum='%s'%(chr(number))
    hoststr=''
    for x in name.split('.'):
        hoststr = hoststr+chr(len(x))+x 
    data = '%s%s\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00%s\x00\x00\x01\x00\x01' % (hexqueryid,hexnum,hoststr)
    return data



class Locallist(object):
    def __init__(self):
        self.dic = {}          
        self.buffer={}         
        self.s_time={}       
        self.sem=1             
        self.Local_Server='202.38.93.153'
        self.Client='127.0.0.1'      
        self.Port=53            
        self.MaxWaitTime=2    
        self.qin=queue.Queue() 
        self.qout=queue.Queue()
        self.sockin=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.sockin.bind((self.Client,self.Port))
        self.sockout=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    def GetSem(self):   
        if(self.sem==1):
            self.sem=0
            return 1
        else:
            return 0
    def ReturnSem(self):   
        if(self.sem==0):
            self.sem=1
        else:
            print('ERROR:SEM')
    def Read_Config(self):              
        configf = open('config.txt', 'r')
        for line in configf.readlines():
            self.dic[(line.strip()).split(' ',1)[1]]=(line.strip()).split(' ',1)[0]
        configf.close()
    def ExternQuery(self,name,queryid,number): 
        data=pack_data_q(name,queryid,number)
        print('EXTERNAL QUERY')
        self.sockout.sendto(bytes(data, encoding = "iso8859"),(self.Local_Server,53))
        msg=self.sockout.recvfrom(1024)         
        self.qout.put(msg)                   
    def timer(self,name,queryid,number,t0):      
        t1=time.time()
        str_queryid=str(queryid)
        while(str_queryid in self.s_time and (t1-t0)<self.MaxWaitTime):
            t1=time.time()
        while(self.GetSem()==0):
            pass
        if(str_queryid in self.s_time):
            if(number==2):
                if((self.s_time[str_queryid])[0]==1):
                    self.s_time[str_queryid]=(2,time.time())
                    print("Timeout")
                    threading.Thread(target=self.timer, args=(name,queryid,3,(self.s_time[str_queryid])[1],)).start()
                    threading.Thread(target=self.ExternQuery, args=(name,queryid,2,)).start()
            elif(number==3):
                if((self.s_time[str_queryid])[0]==2):
                    self.s_time[str_queryid]=(3,time.time())
                    print("Timeout:2")
                    threading.Thread(target=self.timer, args=(name,queryid,4,(self.s_time[str_queryid])[1],)).start()
                    threading.Thread(target=self.ExternQuery, args=(name,queryid,3,)).start()
            elif(number==4):
                if((self.s_time[str_queryid])[0]==3):
                    self.buffer.pop(str_queryid)   
                    self.s_time.pop(str_queryid)
                    print("Timeout:3,stop")      
            self.ReturnSem()
        else:
            print('not timeout') 
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
        if(ip=='0.0.0.0'): 
            data='%s\x81\x83\x00\x01\x00\x00%s\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\xdd\x00\x04%s%s%s%s'%(s1,s2,ip4[0],ip4[1],ip4[2],ip4[3])
        else:
            data='%s\x81\x80\x00\x01\x00\x01%s\xc0\x0c\x00\x01\x00\x01\x00\x00\x00\xdd\x00\x04%s%s%s%s'%(s1,s2,ip4[0],ip4[1],ip4[2],ip4[3])
        b_data=bytes(data, encoding = "iso8859")
        self.sockin.sendto(b_data,addr)
    def ReceivePackin(self):     
        while(1):
            try:
                msg=self.sockin.recvfrom(1024)
                self.qin.put(msg)
            except:
                pass
    def LocalQuery(self,name): 
        if name in self.dic:
            if self.dic[name]=="0.0.0.0":
                print("Domain name doesn't exist")
                return (1,'0.0.0.0')
            else:
                print("Local:",self.dic[name])
                return (1,self.dic[name])
        else:
            return (0,'')
    def PackProcess_In(self):    
        while(1):
            if(not self.qin.empty()):  
                got=self.qin.get()
                msgtodo=got[0]
                addr=got[1]
                if(not(msgtodo[3]==131) and msgtodo[5]==1 and msgtodo[7]==0):
                    q_id=chr(msgtodo[0])+chr(msgtodo[1]) 
                    q_name=''
                    i=12
                    while(msgtodo[i]!=0):
                        i2=i+1+msgtodo[i]
                        q_name=q_name+(msgtodo[i+1:i2]).decode(encoding='iso8859')+'.'
                        i=i2
                    q_name=q_name[0:len(q_name)-1]  
                    print("current_query_is")
                    print(q_name)
                    q_result=self.LocalQuery(q_name) 
                    if(q_result[0]==1):            
                        threading.Thread(target=self.SendBack, args=(msgtodo,q_result[1],addr,)).start()
                    else:                          
                        while(self.GetSem()==0):
                            pass
                        queryid=random.randint(0,99)   
                        while(str(queryid) in self.buffer):
                            queryid=random.randint(0,99)
                        str_queryid=str(queryid)
                        self.buffer[str_queryid]=(q_id,addr)       
                        self.s_time[str_queryid]=(1,time.time())
                        self.ReturnSem()
                        threading.Thread(target=self.timer,args=(q_name,queryid,2,(self.s_time[str_queryid])[1],)).start() 
                        threading.Thread(target=self.ExternQuery, args=(q_name,queryid,1,)).start()  
    def PackProcess_Out(self):     
        while(1):
            if(not self.qout.empty()):
                got=self.qout.get()
                msgtodo=got[0]
                if(msgtodo[7]>=1):         
                    a_id=msgtodo[0]        
                    a_number=msgtodo[1]
                    str_a_id=str(a_id)
                    while(self.GetSem()==0):
                        pass
                    if(not(msgtodo[3]==131)):    
                        if((str_a_id in self.s_time) and (self.s_time[str_a_id])[0]==a_number): 
                            ip=str(msgtodo[-4])+'.'+str(msgtodo[-3])+'.'+str(msgtodo[-2])+'.'+str(msgtodo[-1])
                            r_name=''
                            i=12
                            while(msgtodo[i]!=0):
                                i2=i+1+msgtodo[i]
                                r_name=r_name+msgtodo[i+1:i2].decode(encoding='iso8859')+'.'
                                i=i2
                            r_name=r_name[0:len(r_name)-1]
                            back=self.buffer[str_a_id]
                            back_id=back[0]
                            back_addr=back[1]
                            msgback=back_id+msgtodo[2:].decode(encoding='iso8859')
                            b_msgback=bytes(msgback, encoding = "iso8859")
                            self.sockin.sendto(b_msgback,back_addr)
                            self.buffer.pop(str_a_id)
                            self.s_time.pop(str_a_id)
                            print('ANSWER:',r_name)
                            print('ID:',repr(bytes(back_id, encoding = "iso8859")),'--->',str_a_id)                                         
                    else:  
                        if((str_a_id in self.s_time) and (self.s_time[str_a_id])[0]==a_number):
                            back=self.buffer[str_a_id]
                            back_id=back[0]
                            back_addr=back[1]
                            msgback=back_id+msgtodo[2:].decode(encoding='iso8859')   
                            b_msgback=bytes(msgback, encoding = "iso8859") 
                            self.sockin.sendto(b_msgback,back_addr)
                            self.buffer.pop(str_a_id) 
                            self.s_time.pop(str_a_id)                    
                    self.ReturnSem()
Local=Locallist()
Local.Read_Config()
threading.Thread(target=Local.ReceivePackin).start()
threading.Thread(target=Local.PackProcess_In).start()
threading.Thread(target=Local.PackProcess_Out).start()
