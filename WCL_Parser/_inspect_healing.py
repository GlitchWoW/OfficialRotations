import os,json,urllib.request,urllib.parse
code='Fr1v4QhXNtg8HmTP';fight=1
cid=os.environ['WCL_CLIENT_ID'];sec=os.environ['WCL_CLIENT_SECRET']
body=urllib.parse.urlencode({'grant_type':'client_credentials','client_id':cid,'client_secret':sec}).encode()
req=urllib.request.Request('https://www.warcraftlogs.com/oauth/token',data=body,headers={'Content-Type':'application/x-www-form-urlencoded'})
tok=json.loads(urllib.request.urlopen(req).read().decode())['access_token']

def gql(q,v=None):
 p={'query':q,'variables':v or {}}
 r=urllib.request.Request('https://www.warcraftlogs.com/api/v2/client',data=json.dumps(p).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+tok})
 return json.loads(urllib.request.urlopen(r).read().decode())

q='''query($code:String!,$fightIDs:[Int]){reportData{report(code:$code){fights(fightIDs:$fightIDs){startTime endTime}}}}'''
fi=gql(q,{'code':code,'fightIDs':[fight]})['data']['reportData']['report']['fights'][0]
q2='''query($code:String!,$fightIDs:[Int],$start:Float,$end:Float){reportData{report(code:$code){events(dataType:Healing,fightIDs:$fightIDs,startTime:$start,endTime:$end,useAbilityIDs:true){data}}}}'''
ev=gql(q2,{'code':code,'fightIDs':[fight],'start':fi['startTime'],'end':fi['endTime']})['data']['reportData']['report']['events']['data']
print('events',len(ev))
for e in ev[:20]:
 print(e)
