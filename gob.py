import numpy as np 
from sklearn.metrics.pairwise import rbf_kernel
from sklearn.preprocessing import Normalizer, MinMaxScaler
from scipy.sparse import csgraph 
import scipy


class GOB():
	def __init__(self, dimension, user_num, item_num, pool_size, item_feature_matrix, true_user_feature_matrix, true_payoffs, lap, alpha, delta, sigma, beta):
		self.dimension=dimension
		self.user_num=user_num
		self.item_num=item_num
		self.pool_size=pool_size
		self.item_feature_matrix=item_feature_matrix
		self.true_user_feature_matrix=true_user_feature_matrix
		self.true_payoffs=true_payoffs
		self.true_user_feature_vector=true_user_feature_matrix.flatten()
		self.user_feature_vector=np.zeros(self.user_num*self.dimension)
		self.user_feature_matrix=np.zeros((self.user_num, self.dimension))
		self.I=np.identity(self.user_num*self.dimension)
		self.L=lap+0.01*np.identity(self.user_num)
		self.A=np.kron(self.L, np.identity(self.dimension))
		self.A_inv=np.linalg.pinv(self.A)
		self.A_sqrt=scipy.linalg.sqrtm(self.A)
		self.A_inv_sqrt=scipy.linalg.sqrtm(self.A_inv)
		self.A_sqrt_inv=np.linalg.pinv(self.A_inv_sqrt)
		self.alpha=alpha
		self.delta=delta
		self.sigma=sigma
		self.beta=beta
		self.covariance=self.alpha*np.identity(self.user_num*self.dimension)
		self.bias=np.zeros(self.user_num*self.dimension)
		self.beta_list=[]

	def update_beta(self): #not used
		a=np.linalg.det(self.covariance)**(1/2)
		b=np.linalg.det(self.alpha*self.I)**(-1/2)
		beta=self.sigma*np.sqrt(2*np.log(a*b/self.delta))+np.sqrt(self.alpha)*np.linalg.norm(np.dot(self.A_sqrt,self.true_user_feature_vector))
		self.beta_list.extend([beta])
		
	def select_item(self, item_pool, user_index, time):
		item_fs=self.item_feature_matrix[item_pool]
		item_feature_array=np.zeros((self.pool_size, self.user_num*self.dimension))
		item_feature_array[:,user_index*self.dimension:(user_index+1)*self.dimension]=item_fs
		estimated_payoffs=np.zeros(self.pool_size)
		# self.update_beta()
		self.beta_list.extend([self.beta])
		cov_inv=np.linalg.pinv(self.covariance)
		for j in range(self.pool_size):
			item_index=item_pool[j]
			x=self.item_feature_matrix[item_index]
			x_long=np.zeros((self.dimension*self.user_num))
			x_long[user_index*self.dimension:(user_index+1)*self.dimension]=x
			co_x=np.dot(np.real(self.A_inv_sqrt), x_long)
			x_norm=np.sqrt(np.dot(np.dot(co_x, cov_inv),co_x))
			est_y=np.dot(self.user_feature_vector, co_x)+self.beta*x_norm*np.sqrt(np.log(time+1))
			estimated_payoffs[j]=est_y

		max_index=np.argmax(estimated_payoffs)
		selected_item_index=item_pool[max_index]
		selected_item_feature=item_fs[max_index]
		true_payoff=self.true_payoffs[user_index, selected_item_index]
		max_ideal_payoff=np.max(self.true_payoffs[user_index][item_pool])
		regret=max_ideal_payoff-true_payoff
		return true_payoff, selected_item_feature, regret

	def update_user_feature(self, true_payoff, selected_item_feature, user_index):
		x_long=np.zeros(self.dimension*self.user_num)
		x_long[user_index*self.dimension:(user_index+1)*self.dimension]=selected_item_feature
		co_x=np.dot(np.real(self.A_inv_sqrt), x_long)
		self.covariance+=np.outer(co_x, co_x)
		self.bias+=true_payoff*co_x
		cov_inv=np.linalg.pinv(self.covariance)
		self.user_feature_vector=np.dot(cov_inv, self.bias)
		self.user_feature_matrix=self.user_feature_vector.reshape((self.user_num, self.dimension))

	def run(self, alpha,  user_array, item_pool_array, iteration):
		cumulative_regret=[0]
		learning_error_list=np.zeros(iteration)
		learning_error_list_2=np.zeros(iteration)
		for time in range(iteration):	
			self.alpha=alpha/(time+1)
			print('time/iteration', time, iteration, '~~~GOB')
			user_index=user_array[time]
			item_pool=item_pool_array[time]
			true_payoff, selected_item_feature, regret=self.select_item(item_pool, user_index, time)
			self.update_user_feature(true_payoff, selected_item_feature, user_index)
			cumulative_regret.extend([cumulative_regret[-1]+regret])
			error=np.linalg.norm(np.dot(np.real(self.A_inv_sqrt),self.user_feature_vector)-self.true_user_feature_vector)
			learning_error_list[time]=error

		return np.array(cumulative_regret), learning_error_list, self.beta_list