import json
import pathlib
import random

from ...libraries.tools import *
from ...libraries.pluginmanage.tools import *

ROOT_PATH=pathlib.Path(__file__).resolve().parent.parent.parent.parent #/server
DATA_PATH=ROOT_PATH/"data"/"finaltest"

def listall():
    """获取全部题目集名称"""
    files=(DATA_PATH/"questions").iterdir()
    return [f.stem for f in files]

class Test:
    def __init__(self,question_selection):
        self.selection=question_selection#题目集
        self.questions=[]#题目及答案
        self.test=[]#测试题集
        self.now={}#当前题目
        self.state=[0,0]#状态，正确/错误次数
        self.available=self.generate()#是否可用

    def generate(self):
        """生成题目"""
        if not pathlib.Path.exists(DATA_PATH/"questions"/(self.selection+".json")):
            return False
        self.questions=jsonLoad(DATA_PATH/"questions"/(self.selection+".json"))
        self.test=self.questions+self.questions
        return True
    
    def choose(self):
        """抽取一个题目"""
        if not self.available:
            return {}
        if not self.test:#做完了
            self.available=False
            return {}
        self.now=random.choice(self.test)
        return self.now

    def verify(self,inputs:str):
        """判断是否正确"""
        answer=self.now["answer"]
        ans=[]
        for c in answer:
            if c in ["A","B","C","D"] and not c in ans:
                ans.append(c)
        ips=[]
        for c in inputs.upper():
            if c in ["A","B","C","D"] and not c in ips:
                ips.append(c)
        if len(ans)!=len(ips):
            self.state[1]+=1
            return False
        for a in ips:
            if not a in ans:
                self.state[1]+=1
                return False
        self.test.remove(self.now)#答对了移除题目，答错了保留
        self.state[0]+=1
        return True