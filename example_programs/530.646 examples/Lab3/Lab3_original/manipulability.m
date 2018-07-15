function [ mu ] = manipulability( J, measure )
%manipulability() measures the manipulability of the current ur5 state
%   inputs: 
%   J is the 6x6 body jacobian for the current state
%   measure is a string detailing which measure to use.
%       -options are 'sigmamin' for the minimum sigma value from singular
%       value decomposition, 'detjac' for the determinant of the jacobian,
%       and 'invcond' for the inverse of the condition number (i.e. 
%       sigmamin/sigmamax)
%   outputs:
%       mu is the manipulability under the specified measurement type


    %error checking on input arguements
    dims = size(J);
    
    if size(J) ~= [6 6]
        error('Unrecognized dimensions on J. Expected 6x6, instead found %dx%d', dims(1), dims(2))
    end
    
    
    %compute the manipulability measure based on the measure type specified
    if strcmp(measure, 'sigmamin')
        [U,S,V] = svd(J);
        mu = min(diag(S));
        
    elseif strcmp(measure, 'detjac')
        %do something
        mu = det(J);
        
    elseif strcmp(measure, 'invcond')
        [U,S,V] = svd(J);
        mu = min(diag(S))/max(diag(S));
        
    else
        error('Unrecognized measure ''%s''. Expected ''sigmamin'' ''detjac'' or ''invcond''', measure)
    end


end

