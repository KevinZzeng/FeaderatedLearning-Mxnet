import sys
path_base = "E:\\PythonProjects\\Mxnet_FederatedLearning"
sys.path.append(path_base)
from mxnet import ndarray as nd
import mxnet as mx
from mxnet.gluon import nn
from mxnet import gluon
import socket
import os
import pickle
import numpy as np
import copy
from Tools import utils
from Tools.log import log
import json
import time
from Algorithm.FedAvg import Fed_avg_tool
mx.random.seed(int(time.time()))

class Server_data_handler():
    # 模型管理类
    # 管理服务器端内部参数处理，Server类调用该类方法
    def __init__(self, model, input_shape, learning_rate, update_model_path, init_model_randomly, init_model_path="",):
        # model: MXnet中nn.Block类或其派生类
        # data_shape: 模型输入数据形状
        # learning_rate: Server端接收梯度时的更新学习率
        # random_inital_model: 是否随机生辰初始模型
        # init_model_dir: 随机初始化模型保存路径
        self.__net = model
        self.__ctx = utils.try_all_gpus()
        self.input_shape = input_shape  # 训练数据的形状
        self.learning_rate = learning_rate  # 学习率
        self.updata_model_path = update_model_path
        # log类
        # 存储系统日志信息
        #self.log = log(path_base + "\\Fed_Server\\log")
        if init_model_randomly == True:
            self.__random_init_model()
        else:
            try:
                self.__init_model_file(init_model_path)
            except:
                raise ValueError("Invalid init_model_path")   
            
        # 算法拓展
        self.fed_avg_tool = None
    
    def get_model_info(self):
        return str(self.__net)

    def activate_FedAvg(self, cla):
        self.fed_avg_tool = Fed_avg_tool(self.__net, ctx=self.__ctx, cla=cla)
        
    def __get_deafault_valData(self):
        mnist = mx.test_utils.get_mnist()
        val_data = {"test_data":mnist['test_data'],"test_label":mnist['test_label']}
        return val_data

    def __init_model_file(self,model_path):
        print("-读取初始化模型-")
        print(self.__net)
        self.__net.load_parameters(model_path,ctx=self.__ctx)
        print("-验证Server端初始模型性能-")
        self.validate_current_model(self.__get_deafault_valData())
        self.save_current_model2file(self.updata_model_path)

    def __random_init_model(self):
        print("-随机初始化模型-")
        print(self.__net)
        # 初始化用户自定义的模型
        #self.input_shape,self.__net = self.custom_model()
        self.__net.initialize(mx.init.Xavier(magnitude=2.24),ctx=self.__ctx)
        # Mxnet：神经网络在第一次前向传播时初始化
        # 因此初始化神经网络时需要做一次随机前向传播
        self.__net(nd.random.uniform(shape=self.input_shape,ctx=self.__ctx[0]))
        # 保存初始化模型 Server可发送至Client训练
        #self.__net.save_parameters(save_path)
        print("-验证Server端初始模型性能-")
        self.validate_current_model(self.__get_deafault_valData())
        self.save_current_model2file(self.updata_model_path)

    def validate_current_model(self,val_data_set=None):
        # 给定数据集测试模型性能
        # 评估当前模型准确率
        #val_x,val_y = val_data_set[0],val_data_set[1]
        #val_data = mx.io.NDArrayIter(val_x,val_y,batch_size=100)
        mnist = mx.test_utils.get_mnist()
        val_data = mx.io.NDArrayIter(mnist['test_data'],mnist['test_label'],batch_size=100)
        # 待通用化
        for batch in val_data:
            data = gluon.utils.split_and_load(batch.data[0],ctx_list=self.__ctx,batch_axis=0)
            label = gluon.utils.split_and_load(batch.label[0],ctx_list=self.__ctx,batch_axis=0)
            outputs = []
            metric = mx.metric.Accuracy()  
            for x in data:
                outputs.append(self.__net(x))
            metric.update(label,outputs)
        name,acc = metric.get()
        print('验证集准确率 validation acc:%s=%f'%(name,acc))
        return acc
        
    def __update_gradient(self,gradient_info):
        # 由Client回传的梯度信息 更新Server模型
        idx = 0
        gradient_w = gradient_info['weight']
        gradient_b = gradient_info['bias']
        update_flag = False
        lr = self.learning_rate
        for layer in self.__net:
            try:
                layer.weight.data()[:] -= gradient_w[idx].as_in_context(layer.weight.data().context) * lr
                layer.bias.data()[:] -= gradient_b[idx].as_in_context(layer.bias.data().context) * lr
                if update_flag is False:
                    update_flag = True
            except:
                continue
            idx += 1
        if update_flag:
            print("-gradient successfully updated-")
        else:
            print("-oops! gradient failure-")

    def save_current_model2file(self,save_dir):
        try:
            print("模型保存",save_dir)
            self.__net.save_parameters(save_dir)
        except:
            raise ValueError("Invalid path %s"&save_dir)
        
    def process_data_from_client(self, client_data, mode):
        # mode: replace 模型直接替换 gradient 梯度更新 defined由用户自定义 FedAvg
        print("处理Client回传数据 mode: ",mode)
        if mode=='replace':
            # replace 模式下直接将传回的模型作为当前模型
            self.__net = client_data
            acc = self.validate_current_model()
            self.save_current_model2file(self.updata_model_path)
            return acc
        elif mode=='gradient':
            # gradient 处理Client回传的gradient信息
            self.__update_gradient(client_data)
            acc = self.validate_current_model()
            self.save_current_model2file(self.updata_model_path)
            return acc
        elif mode=='FedAvg':
            # FedAvg
            flg = self.fed_avg_tool.add_fed_model(client_data)
            if flg is True:
                self.fed_avg_tool.get_averaged_model(self.__net)
                self.save_current_model2file(self.updata_model_path)
                acc = self.validate_current_model()
                return acc
            else:
                return -1
        elif mode=='defined':
            # 自定义算法
            self.defined_data_method(client_data)
        else:
            raise ValueError("Invalid mode %s. Options are replace, gradient and defined"&mode)

    def defined_data_method(self,client_data):
        # 用户可重写该函数算法使用处理Client数据
        pass
    
    
