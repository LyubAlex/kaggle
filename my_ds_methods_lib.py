import numpy as np
import pandas as pd

from sklearn.preprocessing import StandardScaler

from sklearn.model_selection import cross_val_score
from sklearn.model_selection import KFold

from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from tqdm import tqdm_notebook as tqdm
# HPO
from skopt.space import Integer, Categorical, Real
from skopt.utils import use_named_args
from skopt import gp_minimize, gbrt_minimize
from skopt.plots import plot_convergence
from skopt.callbacks import DeltaXStopper, DeadlineStopper, DeltaYStopper
from skopt.callbacks import EarlyStopper

def get_params_SKopt(model, X, Y, space):
    cv_search = KFold(n_splits=3, shuffle=True, random_state = 0)
    
    HPO_PARAMS = {'n_calls':500,
                  'n_random_starts':10,
                  'acq_func':'EI',}

    @use_named_args(space)
    def objective(**params):
        model.set_params(**params)
        return -np.mean(cross_val_score(model, 
                                        X, Y, 
                                        cv=cv_search, 
                                        n_jobs = -1, 
                                        scoring='neg_mean_absolute_error'))
    
    reg_gp = gbrt_minimize(objective, 
                           space, 
                           verbose = False,
                           callback = [RepeatedMinStopper(n_best = 30), DeadlineStopper(total_time = 7200)],
                           **HPO_PARAMS,
                           random_state = 0)

    model.max_depth = reg_gp.x[0]
    model.min_child_weight = reg_gp.x[1]
    model.learning_rate = reg_gp.x[2]
    model.subsample = reg_gp.x[3]
    model.colsample_bytree = reg_gp.x[4]
    model.reg_alpha = reg_gp.x[5]
    model.reg_lambda = reg_gp.x[6]

    return [model,reg_gp]

class RepeatedMinStopper(EarlyStopper):
    """Stop the optimization when there is no improvement in the minimum.
    Stop the optimization when there is no improvement in the minimum
    achieved function evaluation after `n_best` iterations.
    """
    def __init__(self, n_best=50):
        super(EarlyStopper, self).__init__()
        self.n_best = n_best
        self.count = 0
        self.minimum = np.finfo(np.float).max

    def _criterion(self, result):
        if result.fun < self.minimum:
            self.minimum = result.fun
            self.count = 0
        elif result.fun > self.minimum:
            self.count = 0
        else:
            self.count += 1

        return self.count >= self.n_best

def simple_FS(threshold, train, test):
    corr_matrix = train.corr().abs()
    upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(np.bool))
    to_drop = [column for column in upper.columns if any(upper[column] > threshold)]
    print('\nThere are %d columns to remove.' % (len(to_drop)))
    train = train.drop(columns = to_drop)
    test = test.drop(columns = to_drop)  
    print (f'After dropping {train.shape[1]}' + ' features remain')   
    return [train, test, to_drop]

def get_nan_col(df, N):
    # Get features with minimum N percentage of null observations 
    n_observ = int(np.round(N*np.size(df, 0)))
    allnull  = df.isnull().sum(axis=0).reset_index()
    lst_del  = [allnull.loc[i,'index'] for i in range(len(allnull)) if allnull.loc[i,0] > n_observ]  
    lst_proc = [allnull.loc[i,'index'] for i in range(len(allnull)) if allnull.loc[i,0] < n_observ and allnull.loc[i,0] > 0]
    return [lst_del, lst_proc]

def smart_fillna (common_df, Y, percent , fill_method_all, model_type, cv, scoring):   
    X = pd.DataFrame()
    X_test = pd.DataFrame()

    if model_type == 'linear':
        model = LinearRegression()
    elif model_type == 'rfr':
        model = RandomForestRegressor(n_estimators = 50, n_jobs = -1)
    
    lst_nan = get_nan_col(common_df, percent)
    print (f'To delete {len(lst_nan[0])}' + ' features')
    print (f'To process {len(lst_nan[1])}' + ' features')
    common_df.drop(lst_nan[0], axis = 1, inplace = True)
       
    if len(lst_nan[1]) > 0:
        print ('Processing features...')
        for feature in tqdm(lst_nan[1]):
            mas_score = []
            best_score = np.inf
            best_method = ''
            
            no_na = common_df.copy()
            no_na.dropna(axis='columns', inplace=True)
            
            for fill_method in fill_method_all:       
                common_df_copy = common_df.copy()

                if fill_method == 'mean':              
                    common_df_copy[feature].fillna(common_df_copy.mean()[feature], inplace = True)  
                elif fill_method == 'median': 
                    common_df_copy[feature].fillna(common_df_copy.median()[feature], inplace = True)  
                elif fill_method == 'interpolation':
                    common_df_copy[feature].fillna(common_df_copy.interpolate()[feature], inplace = True)  
                    
                X_train_feature = common_df_copy[common_df_copy['train'] == 1][feature]           
                X_train_feature = pd.DataFrame(np.nan_to_num(X_train_feature), columns = {feature})
                
                scaler = StandardScaler()
                if model_type == 'linear':
                    scaler.fit(X_train_feature.values.reshape(-1, 1))
                    X_train = scaler.transform(X_train_feature.values.reshape(-1, 1))  
                elif model_type == 'rfr':
                    X_train = X_train_feature.values.reshape(-1, 1)
                
                score = -np.mean(cross_val_score(model, 
                                            X_train, Y,      
                                            cv = cv, 
                                            scoring = scoring))
                mas_score.append(score)

                if score < best_score:
                    best_score = score 
                    best_method = fill_method
                del common_df_copy

            if best_method == 'mean':
                common_df[feature].fillna(common_df.mean()[feature], inplace = True)
            elif best_method == 'median': 
                common_df[feature].fillna(common_df.median()[feature], inplace = True)
            elif best_method == 'interpolation': 
                common_df[feature].fillna(common_df.interpolate()[feature], inplace = True)
            
            del no_na
            
            print(f'Best score:     {best_score}')
            
        X = common_df.loc[common_df['train'] == 1,:]
        X_test = common_df.loc[common_df['train'] == 0,:] 
        
    else:
        print('Zero features with missing values')
        
        X = common_df.loc[common_df['train'] == 1,:]
        X_test = common_df.loc[common_df['train'] == 0,:]
        
    X.drop('train', axis = 1, inplace = True)
    X_test.drop('train', axis = 1, inplace = True)
    return [X, X_test, Y.reset_index(drop=True), lst_nan[1]]    