function [ xi ] = vee( xi_hat )
%vee extracts the 6x1 twist coordinates from a parameterized twist
%   input: xi_hat is a 4x4 screw transformation paramaterized by xi
%   output: xi is the 6x1 vector [v w]' representing the twist coordinates

    dims = size(xi_hat);

    if dims == [4 4]
        v = xi_hat(1:3,4);
        w = [xi_hat(3,2) xi_hat(1,3) xi_hat(2,1)]';
        xi = [v; w];
    else
        error('Unrecognized dimensions on input. Expected 4x4, instead found %dx%d', dims(1), dims(2));
    end



end

