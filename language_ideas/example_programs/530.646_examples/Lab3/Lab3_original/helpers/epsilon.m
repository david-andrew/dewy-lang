function [ e ] = epsilon
%epsilon returns the allowable difference between equivalent float values
%   outputs: e is the value below which the difference between two floating
%   point values is considered to be zero.
%   
%   e.g. if a, b are floats, then abs(a-b) < epsilon will return whether or
%   not a and b are equivalent within numerical precision
    
    e = 1e-10;

end

