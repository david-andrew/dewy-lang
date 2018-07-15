function [ xi_hat ] = wedge( xi )
%vee extracts the 6x1 twist coordinates from a parameterized twist
%   input: xi is the 6x1 vector [v w]' representing the twist coordinates
%   output: xi_hat is a 4x4 screw transformation paramaterized by xi


    dims = size(xi);

    if dims == [6 1]
        v = xi(1:3); w = xi(4:6);
        xi_hat = [hat(w) v; 0 0 0 0];
    else
        error('Unrecognized dimensions on input. Expected 6x1, instead found %dx%d', dims(1), dims(2));
    end



end

