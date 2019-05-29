function [ xi ] = revolute_twist( w, q )
%revolute_twist computes the twist coordinates for a revolute joint
%   inputs: w is a 3x1 vector that represents the axis of the twist.
%       q is a 3x1 point that the axis w passes through
%   output: xi is a 6x1 twist constructed from w and q

    dims_w = size(w);
    dims_q = size(q);

    if dims_w == [3 1] & dims_q == [3 1]
        xi = [-cross(w,q); w];

    else
        error('Unrecognized dimensions on w or q. Expected both 3x1, instead found w: %dx%d and q: %dx%d',...
            dims_w(1), dims_w(2), dims_q(1), dims_q(2));
    end


end

