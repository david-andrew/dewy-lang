function [ x_hat ] = hat( x )
%hat takes a vector and returns the associated matrix from hat-ing it
%   if x is a 3x1 vector, hat(x) returns the skew symmetric cross product 
%   matrix associated with the axis x
%   inputs: x is a 3x1 vector representing an axis of rotation
%   outputs: x_hat is the 3x3 associated skew symmetric matrix of x

    dims = size(x);

    if dims == [3 1]
        %for a vector-> skew symmetric matrix
        x_hat = [0 -x(3) x(2); x(3) 0 -x(1); -x(2) x(1) 0];

    else
        error('Unrecognized dimensions on input. Expected 3x1 or 6x1, instead found %dx%d', dims(1), dims(2));
    end


end

