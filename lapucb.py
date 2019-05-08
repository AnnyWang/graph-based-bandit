import numpy as np 
from sklearn.metrics.pairwise import rbf_kernel
from sklearn.preprocessing import Normalizer, MinMaxScaler
from scipy.sparse import csgraph 
import scipy
import os 

class LAPUCB(): 
	def __init__(self, dimension, user_num, item_num, pool_size, item_feature_matrix, true_user_feature_matrix, true_payoffs, noise_matrix, normed_lap, alpha, delta, sigma):
		self.dimension=dimension
		self.user_num=user_num
		self.item_num=item_num
		self.pool_size=pool_size
		self.item_feature_matrix=item_feature_matrix
		self.true_user_feature_matrix=true_user_feature_matrix
		self.true_payoffs=true_payoffs
		self.noise_matrix=noise_matrix
		self.user_feature_matrix=np.zeros((self.user_num, self.dimension))
		self.adj=np.identity(self.user_num)
		self.L=normed_lap+0.01*np.identity(self.user_num)
		self.A=np.kron(self.L, np.identity(self.dimension))
		self.A_inv=np.linalg.pinv(self.A)
		self.XX=np.zeros((self.user_num*self.dimension, self.user_num*self.dimension))
		self.alpha=alpha
		self.delta=delta
		self.sigma=sigma
		self.beta=0
		self.cov=self.alpha*self.A
		self.cov_inv=np.linalg.pinv(self.cov)
		self.bias=np.zeros((self.user_num*self.dimension))
		self.beta_list=[]
		self.user_v={}
		self.user_avg={}
		self.user_ls=np.zeros((self.user_num, self.dimension))
		self.user_xx={}
		self.user_bias={}

	def initialized_parameter(self):
		for u in range(self.user_num):
			self.user_v[u]=self.alpha*np.identity(self.dimension)
			self.user_avg[u]=np.zeros(self.dimension)
			self.user_xx[u]=0.01*np.identity(self.dimension)
			self.user_bias[u]=np.zeros(self.dimension)

	def update_beta(self, user_index):
		a=np.linalg.det(self.user_v[user_index])**(1/2)
		b=np.linalg.det(self.alpha*np.identity(self.dimension))**(-1/2)
		d=self.sigma*np.sqrt(2*np.log(a*b/self.delta))
		c=self.alpha*np.sqrt(np.trace(np.linalg.pinv(self.user_v[user_index])))*np.linalg.norm(self.user_feature_matrix[user_index]-self.user_avg[user_index])
		self.beta=c+d
		self.beta_list.extend([self.beta])

	def select_item(self, item_pool, user_index, time):
		item_fs=self.item_feature_matrix[item_pool]
		estimated_payoffs=np.zeros(self.pool_size)
		self.update_beta(user_index)
		v_inv=np.linalg.pinv(self.user_v[user_index])
		for j in range(self.pool_size):
			x=item_fs[j]
			x_norm=np.sqrt(np.dot(np.dot(x, v_inv),x))
			est_y=np.dot(x, self.user_feature_matrix[user_index])+self.beta*x_norm
			estimated_payoffs[j]=est_y

		max_index=np.argmax(estimated_payoffs)
		selected_item_index=item_pool[max_index]
		selected_item_feature=item_fs[max_index]
		true_payoff=self.true_payoffs[user_index, selected_item_index]
		max_ideal_payoff=np.max(self.true_payoffs[user_index][item_pool])
		regret=max_ideal_payoff-true_payoff
		return true_payoff, selected_item_feature, regret

	def update_user_feature(self, true_payoff, selected_item_feature, user_index):
		x_long=np.zeros((self.user_num*self.dimension))
		x_long[user_index*self.dimension:(user_index+1)*self.dimension]=selected_item_feature
		self.user_v[user_index]+=np.outer(selected_item_feature, selected_item_feature)
		self.cov+=np.outer(x_long, x_long)
		self.XX+=np.outer(x_long, x_long)
		self.bias+=true_payoff*x_long
		self.cov_inv=np.linalg.pinv(self.cov)
		self.user_feature_matrix=np.dot(self.cov_inv, self.bias).reshape((self.user_num, self.dimension))
		self.user_xx[user_index]+=np.outer(selected_item_feature, selected_item_feature)
		self.user_bias[user_index]+=true_payoff*selected_item_feature
		self.user_ls[user_index]=np.dot(np.linalg.pinv(self.user_v[user_index]), self.user_bias[user_index])
		self.user_avg[user_index]=np.dot(self.user_ls.T, -self.L[user_index])+self.user_ls[user_index]

	def update_graph(self, user_index):
		adj_row=rbf_kernel(self.user_ls[user_index].reshape(1,-1), self.user_ls)
		self.adj[user_index]=adj_row
		self.adj[:,user_index]=adj_row
		normed_lap=csgraph.laplacian(self.adj, normed=True)
		self.L=normed_lap+0.01*np.identity(self.user_num)
		self.A=np.kron(self.L, np.identity(self.dimension))
		self.cov=self.XX+self.A

	def run(self,  user_array, item_pool_array, iteration):
		self.initialized_parameter()
		cumulative_regret=[0]
		learning_error_list=np.zeros(iteration)
		for time in range(iteration):	
			print('time/iteration', time, iteration,'~~~LAPUCB')
			user_index=user_array[time]
			item_pool=item_pool_array[time]
			true_payoff, selected_item_feature, regret=self.select_item(item_pool,user_index, time)
			self.update_user_feature(true_payoff, selected_item_feature, user_index)
			self.update_graph(user_index)
			error=np.linalg.norm(self.user_feature_matrix-self.true_user_feature_matrix)
			cumulative_regret.extend([cumulative_regret[-1]+regret])
			learning_error_list[time]=error 

		return np.array(cumulative_regret), learning_error_list, self.beta_list