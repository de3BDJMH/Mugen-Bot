import math

DATA_UNIT={0:"B",
           10:"KB",
           20:"MB",
           30:"GB",
           40:"TB",
           50:"PB",
           60:"EB",
           70:"ZB",
           80:"YB",
           90:"BB",
           100:"NB",
           110:"DB",
           120:"CB"}

class Data:
    def __init__(self,data:list[int|float],zero:bool=False):
        """zero为true时，该data大小=0B"""
        self.base=data[0]
        self.addition=data[1]
        self.is_zero=zero
        if zero:
            self.unit="B"
            self.display="0B"
        elif data[0]<0:#及时纠正错误，这样传入错误数值也能修复了
            self.unit="B"
            self.display="0B"
            self.is_zero=True
        else:
            self.unit=DATA_UNIT[self.base]
            self.display=f"{round(2**data[1],2)}{self.unit}"
    
    def getBytes(self):
        """获取字节数"""
        if self.is_zero:
            return 0
        return int((2**self.base)*(2**self.addition))

    def up(self):
        """向上走一个单位"""
        self.base+=10
        self.addition-=10
    
    def down(self):
        """向下走一个单位"""
        self.base-=10
        self.addition+=10

    def reload(self):
        """计算完成后使用该函数更新unit和display"""
        if self.is_zero:
            self.unit="B"
            self.display="0B"
        elif self.base<0:
            self.unit="B"
            self.display="0B"
            self.is_zero=True
        else:
            self.unit=DATA_UNIT[self.base]
            self.display=f"{round(2**self.addition,2)}{self.unit}"

def plus(a:Data,b:Data):
    """Data相加"""
    if a.is_zero:
        return b
    if b.is_zero:
        return a
    #备份
    ac=Data([a.base,a.addition],a.is_zero)
    bc=Data([b.base,b.addition],b.is_zero)
    if ac.base<bc.base:#保证数量级a>b
        ac,bc=bc,ac
    while bc.base<ac.base:
        bc.up()
    ans=Data([ac.base,ac.addition],ac.is_zero)
    ans.addition=math.log2(2**ac.addition+2**bc.addition)
    while ans.addition>=10:#统一单位
        ans.base+=10
        ans.addition-=10
    ans.reload()
    return ans

def substract(a:Data,b:Data):
    """Data相减"""
    #不交换顺序，小于0的都返回0
    if a.is_zero or b.is_zero:
        return a
    if a.base<b.base or (a.base==b.base and a.addition<=b.addition):
        return Data([0,0],True)
    ac=Data([a.base,a.addition],a.is_zero)
    bc=Data([b.base,b.addition],b.is_zero)
    while bc.base<ac.base:
        bc.up()
    ans=Data([ac.base,ac.addition],ac.is_zero)
    ans.addition=math.log2(2**ac.addition-2**bc.addition)
    while ans.addition<0:
        ans.base-=10
        ans.addition+=10
    ans.reload()
    return ans

def exponent(base:Data,e:float|int):
    """将data进行e次方"""
    if base.is_zero:
        return base
    datae=base.base+base.addition
    datae*=e
    return Data([datae//10*10,datae%10])