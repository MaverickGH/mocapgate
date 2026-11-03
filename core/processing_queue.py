"""Persistent sequential processing queue; interrupted runs require explicit resume."""
import json
import threading
import time

class ProcessingQueue:
    def __init__(self,studio):
        self.studio=studio;self.lock=threading.RLock();self.paused=True;self.stopped=False
        self.path=studio.library()/'.processing-queue.json'
        try:self.items=json.loads(self.path.read_text(encoding='utf-8'))
        except (FileNotFoundError,ValueError):self.items=[]  # повреждённая очередь — начать заново, а не упасть
        for item in self.items:
            if item['state']=='running':item['state']='interrupted'
        self.save()
        threading.Thread(target=self.loop,daemon=True).start()
    def save(self):
        if not self.items and not self.path.exists():return
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_suffix('.tmp');tmp.write_text(json.dumps(self.items,ensure_ascii=False),encoding='utf-8');tmp.replace(self.path)
    def state(self):
        with self.lock:return {'paused':self.paused,'items':[dict(i) for i in self.items]}
    def enqueue(self,tid):
        self.studio.take_dir(tid)
        with self.lock:
            if any(i['id']==tid and i['state'] in ('waiting','running') for i in self.items):raise ValueError('Дубль уже в очереди')
            # пользователь сам поставил дубль в очередь — запускаем её, а не ждём кнопки в свёрнутой панели
            waiting=any(i['state']=='waiting' for i in self.items)
            # пользователь сам поставил дубль в очередь — запускаем её; осознанную паузу с ожидающими не снимаем
            self.items.append({'id':tid,'state':'waiting'})
            if not waiting:self.paused=False
            self.save()
    def command(self,action,tid=None):
        with self.lock:
            if action=='resume':
                self.paused=False
                for i in self.items:
                    if i['state']=='interrupted':i['state']='waiting'
            elif action=='pause':self.paused=True
            elif action=='remove':
                self.items=[i for i in self.items if not(i['id']==tid and i['state']!='running')]
            else:raise ValueError('queue: resume | pause | remove')
            self.save()
    def forget(self,tid):
        """Убрать все записи удалённого дубля — очередь не должна ссылаться на несуществующую папку."""
        with self.lock:
            self.items=[i for i in self.items if i['id']!=tid];self.save()
    def tick(self):
        with self.lock:
            active=next((i for i in self.items if i['state']=='running'),None)
            if active:
                job=self.studio.jobs.get(active.get('job'))
                if job and job.code is not None:
                    active['state']='cancelled' if job.cancelled else 'done' if job.code==0 else 'failed';active['code']=job.code;self.save()
                return
            if self.studio.library()!=self.path.parent:
                self.paused=True;return
            if self.paused or self.studio.busy():return
            if any(j.code is None and j.name.startswith('setup-') for j in self.studio.jobs.values()):return
            item=next((i for i in self.items if i['state']=='waiting'),None)
            if item:
                try:
                    job=self.studio.process(item['id']);item.update(state='running',job=job.id)
                except Exception as e:item.update(state='failed',error=str(e))
                self.save()
    def close(self):
        with self.lock:
            self.paused=True;self.stopped=True
            for item in self.items:
                if item['state']=='running':item['state']='interrupted'
            self.save()
    def loop(self):
        while not self.stopped:
            try:self.tick()
            except Exception:self.paused=True
            time.sleep(.5)
