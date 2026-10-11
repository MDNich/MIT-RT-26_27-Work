%% SimpleServos %%
% Create simple servos object

function [servos] = simple_servos()
    servos = Servos();
    %----------------------------------------------------------------------
    %%% Function assignments %%%
    
    servos.calc_delta = @calc_delta;

    %----------------------------------------------------------------------
    %%% calc_delta %%%
    
        function [delta] = calc_delta(delta, deltastar)
            delta = deltastar;
        end
    
    %%% End calc_delta %%%
    %----------------------------------------------------------------------

end