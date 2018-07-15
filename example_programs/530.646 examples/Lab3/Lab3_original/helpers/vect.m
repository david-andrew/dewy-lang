function [ x ] = vect( x_hat )
%vect performs the inverse operation of the hat() function
%   inputs: x_hat is a 3x3 skew symmetric cross product matrix
%   outpusts: x is the 3x1 axis about which x_hat rotates

    dims = size(x_hat)
    
    if dims == [3 3]
        x = [x_hat(3,2) x_hat(1,3) x_hat(2,1)]';
    else
        error('Unrecognized dimensions on g. Expected 4x4, instead found %dx%d', dims(1), dims(2));
    end


end

