from Fed_Server import Server_data_handler
from Fed_Server import Server
from Algorithm import CNN

model = CNN.CNN_Model("LeNet")
shape = (1,1,28,28)
handler = Server_data_handler.Server_data_handler(model=model,input_shape=shape,learning_rate=0.01,random_initial_model=True)
Serv = Server.Sever(handler)
Serv.listen()