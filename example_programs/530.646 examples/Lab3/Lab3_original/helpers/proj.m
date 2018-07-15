function [ result ] = proj(a, b)
%proj(a,b) projects the vector b onto a
%   inputs:
%       a is a vector
%       b is the vector to project onto a
% 
%   output:
%       result is the result of the projection operation 

    result = (dot(a,b)/dot(a,a)) * a;


end

