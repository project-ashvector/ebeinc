import json, os, tempfile, unittest
from aiohttp.test_utils import AioHTTPTestCase
from app import create_app
class RealtimeTest(AioHTTPTestCase):
 async def get_application(self): self.tmp=tempfile.TemporaryDirectory();os.environ['ALLOWED_ORIGINS']='https://allthings140-visuals-green.pages.dev';return create_app(self.tmp.name+'/state.db')
 async def event(self,ws,kind):
  for _ in range(8):
   value=await ws.receive_json()
   if value.get('type')==kind:return value
  self.fail(f'event {kind} not received')
 async def test_health_chat_reaction_and_limits(self):
  response=await self.client.get('/health');self.assertEqual(response.status,200);self.assertTrue((await response.json())['ok'])
  state=await self.client.get('/visuals-state',headers={'Origin':'https://allthings140-visuals-green.pages.dev'});self.assertEqual(state.status,200);self.assertEqual(state.headers.get('Access-Control-Allow-Origin'),'https://allthings140-visuals-green.pages.dev')
  ws=await self.client.ws_connect('/ws',origin='https://allthings140-visuals-green.pages.dev');welcome=await ws.receive_json();self.assertEqual(welcome['type'],'welcome')
  await ws.send_json({'type':'join','name':'<b>Bass</b>','avatar':'orb-fire'});await self.event(ws,'room_state')
  await ws.send_json({'type':'message','text':'<script>x</script>hello'});event=await self.event(ws,'message');self.assertNotIn('<',event['message']['text'])
  await ws.send_json({'type':'reaction','reaction':'fire','event_id':'one'});event=await self.event(ws,'reaction');self.assertGreater(event['energy'],0)
  await ws.send_json({'type':'reaction','reaction':'fire','event_id':'one'}); # replay ignored
  await ws.send_json({'type':'ping'});pong=await self.event(ws,'pong');await ws.close()
if __name__=='__main__':unittest.main()
