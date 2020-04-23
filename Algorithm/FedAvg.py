from mxnet import gluon
from mxnet.gluon import nn
from mxnet import ndarray as nd
import copy

class Fed_avg_tool():
    # Federated Averaging 算法
    # from paper Communication-Efficient Learning of Deep Networks from Decentralized Data
    def __init__(self, init_model, ctx, cla):
        # init_model初始化存储权值的模型
        self.model_cnt = 0
        self.merge_model = copy.deepcopy(init_model)
        self.__ctx = ctx
        self.cla = cla
        self.__set_model_weight2zero()
        

    def __set_model_weight2zero(self):
        set_flag = False
        for layer in self.merge_model:
            try:
                zero_w = nd.zeros(shape=layer.weight.data().shape,ctx=self.__ctx[0])
                layer.weight.data()[:] = zero_w[:]
                zero_b = nd.zeros(shape=layer.bias.data().shape,ctx=self.__ctx[0])
                layer.bias.data()[:] = zero_b[:]
                if set_flag is False:
                    set_flag = True
            except:
                continue
        
        if set_flag:
            print("FedAvg: 模型参数归零")
        else:
            raise Exception("FedAvg: 模型参数归零失败")
                
    def add_fed_model(self, model):
        add_flag = False
        # 将接收的model weight加入fed_avg model中
        layer_idx = 0
        for layer in self.merge_model:
            try:
                layer.weight.data()[:] += model[layer_idx].weight.data()[:]
                layer.bias.data()[:] += model[layer_idx].bias.data()[:]
                if add_flag is False:
                    add_flag = True
            except:
                continue
            layer_idx += 1
        self.model_cnt += 1
        if add_flag:
            print("FedAvg: 添加模型成功")
            #print(self.merge_model[2].weight.data()[0])
            #print((self.merge_model[2].weight.data()[:]/5)[0])
        else:
            raise Exception("FedAvg: 添加模型失败")
        if(self.model_cnt == self.cla):
            return True
        else:
            return False
        
    def get_averaged_model(self, net):
        average_flag = False
        id = 0
        for layer in net:
            try:
                # 算术平均
                layer.weight.data()[:] = self.merge_model[id].weight.data()[:]/self.model_cnt      
                layer.bias.data()[:] = self.merge_model[id].bias.data()[:]/self.model_cnt
                if average_flag is False:
                    average_flag = True
            except:
                continue
            id += 1
        # 数据初始化
        print("avg: chk")
        print(net[2].weight.data()[0])
        self.__set_model_weight2zero()
        print("avg: chk2")
        print(net[2].weight.data()[0])
        self.model_cnt=0
        if average_flag:
            print("FedAvg: 模型参数加权平均完成")
        else:
            raise Exception("FedAvg: 模型参数加权平均模型失败")

    def chk_cla(self):
        if self.cla == self.model_cnt:
            return True
        else:
            return False