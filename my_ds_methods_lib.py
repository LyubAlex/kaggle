import numpy as np
import pandas as pd

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from sklearn.preprocessing import StandardScaler, normalize

from sklearn.model_selection import cross_val_score
from sklearn.model_selection import KFold

from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from tqdm import tqdm_notebook as tqdm

import seaborn as sns
from mpl_toolkits.mplot3d import Axes3D

# HPO
from skopt.space import Integer, Categorical, Real
from skopt.utils import use_named_args
from skopt import gp_minimize, gbrt_minimize, forest_minimize
from skopt.plots import plot_convergence
from skopt.callbacks import DeltaXStopper, DeadlineStopper, DeltaYStopper
from skopt.callbacks import EarlyStopper


# def get_params_SKopt(model, X, Y, space, cv_search, opt_method = 'gbrt_minimize', verbose = True,  multi = False, scoring = 'neg_mean_squared_error', n_best = 50, total_time = 7200):
   
#     from skopt import Optimizer
#     from sklearn.externals.joblib import Parallel, delayed  
#     from joblib import Parallel, delayed 

#     @use_named_args(space)
#     def objective(**params):
#         model.set_params(**params)
#         return -np.mean(cross_val_score(model, 
#                                         X, Y, 
#                                         cv=cv_search, 
#                                         scoring= scoring))

#     optimizer = Optimizer( dimensions=space,
#                            random_state=1,
#                            base_estimator='gbrt',)
    
#     n_points = multiprocessing.cpu_count()-1
#     x = optimizer.ask(n_points = n_points)  # x is a list of n_points points    
#     y = Parallel(n_jobs = n_points)(delayed(objective)(v) for v in x)  # evaluate points in parallel
#     optimizer.tell(x, y)
    
#     print(optimizer.Xi)
#     print(min(optimizer.yi))  # print the best objective found 

def get_params_SKopt(model, X, Y, space, cv_search, alg = 'catboost', cat_features = None, eval_dataset = None, UBM = False, opt_method =
                     'gbrt_minimize', verbose = True,  multi = False, scoring = 'neg_mean_squared_error', n_best = 50, total_time = 7200):
    """The method performs parameters tuning of an algorithm using scikit-optimize library.
    Parameters:
    1.
    2.
    3. multi - boolean, is used when a multioutput algorithm is tuned
    UPDATES:
    1. In this current version, the support of the catboost algorithms is added
    """
    if alg == 'catboost':
        fitparam = { 'eval_set' : eval_dataset,
                     'use_best_model' : UBM,
                     'cat_features' : cat_features,
                     'early_stopping_rounds': 20 }
    else:
        fitparam = {}
        
    @use_named_args(space)
    def objective(**params):
        model.set_params(**params)
        return -np.mean(cross_val_score(model, 
                                        X, Y, 
                                        cv=cv_search, 
                                        scoring= scoring,
                                        fit_params=fitparam))
    
    if opt_method == 'gbrt_minimize':
        
        HPO_PARAMS = {'n_calls':1000,
                      'n_random_starts':20,
                      'acq_func':'EI',}
        
        reg_gp = gbrt_minimize(objective, 
                               space, 
                               n_jobs = -1,
                               verbose = verbose,
                               callback = [DeltaYStopper(delta = 0.01, n_best = 5), RepeatedMinStopper(n_best = n_best), DeadlineStopper(total_time = total_time)],
                               **HPO_PARAMS,
                               random_state = RANDOM_STATE)
        

    elif opt_method == 'forest_minimize':
        
        HPO_PARAMS = {'n_calls':1000,
                      'n_random_starts':20,
                      'acq_func':'EI',}
        
        reg_gp = forest_minimize(objective, 
                               space, 
                               n_jobs = -1,
                               verbose = verbose,
                               callback = [RepeatedMinStopper(n_best = n_best), DeadlineStopper(total_time = total_time)],
                               **HPO_PARAMS,
                               random_state = RANDOM_STATE)
        
    elif opt_method == 'gp_minimize':
        
        HPO_PARAMS = {'n_calls':1000,
                      'n_random_starts':20,
                      'acq_func':'gp_hedge',}        
        
        reg_gp = gp_minimize(objective, 
                               space, 
                               n_jobs = -1,
                               verbose = verbose,
                               callback = [RepeatedMinStopper(n_best = n_best), DeadlineStopper(total_time = total_time)],
                               **HPO_PARAMS,
                               random_state = RANDOM_STATE)
    
    TUNED_PARAMS = {} 
    for i, item in enumerate(space):
        if multi:
            TUNED_PARAMS[item.name.split('__')[1]] = reg_gp.x[i]
        else:
            TUNED_PARAMS[item.name] = reg_gp.x[i]
    
    return [TUNED_PARAMS,reg_gp]

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

def plotCorrelationMatrix(df, graphWidth):
    df = df.dropna('columns') # drop columns with NaN
    df = df[[col for col in df if df[col].nunique() > 1]] # keep columns where there are more than 1 unique values
#     print('%.0f features of the dataset are considered' % df.shape[1])
    if df.shape[1] < 2:
        print(f'No correlation plots shown: The number of non-NaN or constant columns ({df.shape[1]}) is less than 2')
        return
    corr = df.corr()
    plt.figure(num=None, figsize=(graphWidth, graphWidth), dpi=80, facecolor='w', edgecolor='k')
    
    fmt = lambda x,pos: '{:.0%}'.format(x)
    sns.heatmap(corr, square=True, annot=True, cmap='RdYlGn', annot_kws={"size": 10}, fmt='.1f')
    
    plt.xticks(range(len(corr.columns)), corr.columns, rotation=90)
    plt.yticks(range(len(corr.columns)), corr.columns)
    plt.gca().xaxis.tick_bottom()
    plt.show()
    
def simple_FS(threshold, train, test, verbose = True):
    corr_matrix = train.corr().abs()
    upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(np.bool))
    to_drop = [column for column in upper.columns if any(upper[column] > threshold)]
    train = train.drop(columns = to_drop)
    test = test.drop(columns = to_drop)  
    if verbose:
        print('\nThere are %d columns to remove.' % (len(to_drop)))
        print (f'After dropping {train.shape[1]}' + ' features remain')   
    return [train, test, to_drop]

def features_to_drop(df, verbose = True):
    drop_list = []
    for col_i in df.columns:
        if (df[col_i].nunique() in [1]) and (df[col_i].unique() == 0):
            drop_list.append(col_i)
    if verbose:
        print('Total number of columns to drop:',len(drop_list))
    return drop_list

def get_nan_col(df, N):
    # Get features with minimum N percentage of null observations 
    n_observ = int(np.round(N*np.size(df, 0)))
    allnull  = df.isnull().sum(axis=0).reset_index()
    lst_del  = [allnull.loc[i,'index'] for i in range(len(allnull)) if allnull.loc[i,0] > n_observ]  
    lst_proc = [allnull.loc[i,'index'] for i in range(len(allnull)) if allnull.loc[i,0] < n_observ and allnull.loc[i,0] > 0]
    return [lst_del, lst_proc]

def drop_outliers(mas, use_method = 'Z'):
    res_idx = []
        
    fig, ax = plt.subplots(1, 2, figsize=(15,5))

    z = np.abs(stats.zscore(mas))
    idx_out = [i for i, z_score in enumerate(z) if z_score >= 3]
    idx_rest = [i for i, z_score in enumerate(z) if z_score < 3]
    
    if use_method == 'Z':
        res_idx = idx_rest
    
    ax[0].scatter(idx_rest, mas[idx_rest], linewidths = 0.1)
    ax[0].scatter(idx_out, mas[idx_out], c='r', marker ='*', linewidths = 2)
    ax[0].set_title('Z-score')
    ax[0].set_xlabel('Number of values')
    ax[0].set_ylabel('Value')
    ax[0].grid(True)
    
    Q1, Q3= np.percentile(mas,[25,75])
    IQR = Q3 - Q1
    lower_bound = Q1 -(1.5 * IQR) 
    upper_bound = Q3 +(1.5 * IQR)
    
    idx_out = [i for i, mas_i in enumerate(mas) if (mas_i > upper_bound or mas_i < lower_bound)]
    idx_rest = [i for i, mas_i in enumerate(mas) if (mas_i <= upper_bound and mas_i >= lower_bound)]
    
    if use_method == 'IQR':
        res_idx = idx_rest
        
    ax[1].scatter(idx_rest, mas[idx_rest], linewidths = 0.1)
    ax[1].scatter(idx_out, mas[idx_out], c='r', marker ='*', linewidths = 2)
    ax[1].set_title('IQR-score')
    ax[1].set_xlabel('Number of values')
    ax[1].set_ylabel('Value')
    ax[1].grid(True)
    plt.show()
    
    return res_idx

def std_norm(train, test, cat_names, func = 'std', common_scaler = True):
    
    if func == 'std':
        if len(cat_names) == 0:
            names = train.columns
            scaler = StandardScaler()
            scaler.fit(train)
            train = pd.DataFrame(scaler.transform(train), columns = names)  
        else:
            col_notcat = [c for c in train.columns if c not in cat_names]
            scaler = StandardScaler()
            scaler.fit(train[col_notcat])
           
            train_scaled = scaler.transform(train[col_notcat])              
            old = pd.DataFrame(train[cat_names], columns=cat_names)  
            new = pd.DataFrame(train_scaled, columns=col_notcat, index = old.index)  
            train = pd.concat([new, old], axis = 1)
            
        
        if common_scaler:
            if len(cat_names) == 0:
                names = test.columns
                test = pd.DataFrame(scaler.transform(test) , columns = names) 
            else:        
                test_scaled = scaler.transform(test[col_notcat])  
                old = pd.DataFrame(test[cat_names], columns=cat_names)  
                new = pd.DataFrame(test_scaled, columns=col_notcat, index = old.index)  
                test = pd.concat([new, old], axis = 1)
        else:
            if len(cat_names) == 0:
                names = test.columns
                scaler = StandardScaler()
                scaler.fit(test)
                test = pd.DataFrame(scaler.transform(test) , columns = names)                
            else:
                scaler = StandardScaler()
                scaler.fit(test[col_notcat]) 

                test_scaled = scaler.transform(test[col_notcat])  
                old = pd.DataFrame(test[cat_names], columns=cat_names)  
                new = pd.DataFrame(test_scaled, columns=col_notcat, index = old.index)  
                test = pd.concat([new, old], axis = 1)
                
    elif func == 'norm':      
        
        if len(cat_names) == 0:
            names = train.columns           
            train = pd.DataFrame(normalize(train), columns = names)  
            test  = pd.DataFrame(normalize(test),  columns = names)  
            
        else:
            col_notcat = [c for c in train.columns if c not in cat_names]

            train_norm = normalize(train[col_notcat], axis = 0)
 
            old = pd.DataFrame(train[cat_names], columns=cat_names)
            new = pd.DataFrame(train_norm, columns=col_notcat, index = old.index) 
            train = pd.concat([new, old], axis = 1)
            
            test_norm  = normalize(test[col_notcat],  axis = 0)                    
            old = pd.DataFrame(test[cat_names], columns=cat_names)
            new = pd.DataFrame(test_norm, columns=col_notcat, index = old.index) 
            test = pd.concat([new, old], axis = 1)
    
    return [train, test]

def clean_inf_nan(df):
    return df.replace([np.inf, -np.inf], np.nan)  

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
                if common_df[feature].isnull().values.any():
                    common_df[feature].fillna(common_df.median()[feature], inplace = True)
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

def stat_intervals(stat, alpha):
    boundaries = np.percentile(stat, [100 * alpha / 2., 100 * (1 - alpha / 2.)])
    return boundaries

def get_bootstrap_samples(data, n_samples):
    indices = np.random.randint(0, len(data), (n_samples, len(data)))
    samples = data[indices]
    return samples

def bootstrap_fun(data1, data2, num_of_samples = 500, method = 'mean'):
    np.random.seed(0)
    data1_mean, data2_mean = np.empty(num_of_samples), np.empty(num_of_samples)

    data1_sample = get_bootstrap_samples(data1, num_of_samples)
    data2_sample = get_bootstrap_samples(data2, num_of_samples)
    
    if method == 'mean':
        for i in range(num_of_samples):
            data1_mean[i], data2_mean[i] = data1_sample[i].mean(), data2_sample[i].mean() 
    elif method == 'median':
        for i in range(num_of_samples):
            data1_mean[i], data2_mean[i] = np.median(data1_sample[i]), np.median(data2_sample[i])   
    return data1_mean, data2_mean

def plot_2d_3d(y_2d =[], y_3d = [], X_pca2d = [], X_pca3d = [],  plot_title = '', subtitle1 = '2 PCA components', subtitle2 = '3 PCA components' ):

    fig = make_subplots(
        rows=1, cols=2,
        specs= [
                 [{"type": "xy"}, {"type": "scatter3d"}],
               ],
        subplot_titles=( subtitle1, subtitle2),
        column_widths=[0.4, 0.6]
    )
    
    if isinstance(y_2d, pd.DataFrame):

        df2d = pd.concat([pd.DataFrame(X_pca2d, columns = ['comp1', 'comp2']), y_2d], axis = 1)
        
        df3d = pd.concat([pd.DataFrame(X_pca3d, columns = ['comp1', 'comp2', 'comp3']), y_3d], axis = 1)
        
    else:

        df2d = pd.concat([pd.DataFrame(X_pca2d, columns = ['comp1', 'comp2']), 
                  pd.DataFrame(y_2d, columns = ['target'])], axis = 1)
        
        df3d = pd.concat([pd.DataFrame(X_pca3d, columns = ['comp1', 'comp2', 'comp3']), 
                  pd.DataFrame(y_3d, columns = ['target'])], axis = 1)
    
    trace2D = go.Scatter(x = df2d.comp1,
                         y = df2d.comp2,
                         mode = 'markers',
                         marker = dict(size = 10, color = df2d.target)
                          )

    fig.add_trace(trace2D,
                  row=1, col=1)

    trace3D = go.Scatter3d(x = df3d.comp1,
                           y = df3d.comp2,
                           z = df3d.comp3,
                           mode = 'markers',
                           marker = dict(size = 10, color = df3d.target)
                          )

    fig.add_trace(trace3D,
                  row=1, col=2)
    fig.update_yaxes(automargin=True)

    fig['layout']['xaxis1'].update(title = 'comp_1')
    fig['layout']['yaxis1'].update(title= 'comp_2')

    fig.update_layout(template=None,
        showlegend=False, title = plot_title, title_x=0.5,
                      scene = dict(
                        xaxis_title='comp_1',
                        yaxis_title='comp_2',
                        zaxis_title='comp_3'),

                     )
    fig.show()

def plot_3d_space(X, y, label='Classes'):   
    colors = ['#1F77B4', '#FF7F0E']
    markers = ['o', 's']
    
    fig = plt.figure(figsize=(10,8))
    ax = fig.add_subplot(111, projection='3d')
    
    for l, c, m in zip(np.unique(y), colors, markers):
        ax.scatter(X[y==l, 0], X[y==l, 1], X[y==l, 2], c=c, label=l, marker=m)
        
    ax.set_xlabel('Comp_1')
    ax.set_ylabel('Comp_2')
    ax.set_zlabel('Comp_3')
    plt.title(label)
    plt.legend(loc='upper right')
    plt.show()  


def plot_2d_space(X, y, label='Classes'):   
    colors = ['#1F77B4', '#FF7F0E']
    markers = ['o', 's']
    
    for l, c, m in zip(np.unique(y), colors, markers):
        plt.scatter(X[y==l, 0], X[y==l, 1], c=c, label=l, marker=m)
    plt.title(label)
    plt.legend(loc='upper right')
    plt.show()               
