%% SimpleController %%
% Create simple Controller object

function [ctrl] = simple_controller()

    ctrl = Controller();
    
    %----------------------------------------------------------------------
    %%% Function assignments %%%
    
    ctrl.calc_deltastar = @calc_deltastar;
    ctrl.initialize_log = @initialize_log;
    ctrl.log_data = @log_data;
    %----------------------------------------------------------------------
    %%% calc_deltastar %%%
    
    function [deltastar] = calc_deltastar(omegahat, Vdothat)
        deltastar = [0; 0; 0];
    end
    
    %%% End calc_deltastar %%%
    %----------------------------------------------------------------------
    %%% initialize_log %%%
    
    function [] = initialize_log(self, N)
        clog = struct();
        clog.deltastar = zeros(3, N);

        self.clog = clog;
    end
    
    %%% End initialize_log %%%
    %----------------------------------------------------------------------
    %%% log_data %%%

    function log_data(self, k)
        self.clog.deltastar(:, k) = [0;0;0];  
    end

    %%% End log_data %%%

end