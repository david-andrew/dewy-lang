function [ xi ] = prismatic_twist( v )
%prismatic_twist computes the twist coordinates for a prismatic joint
%   inputs: v is a 3x1 vector that represents the vactor of translation
%   output: xi is a 6x1 twist constructed from v

    dims = size(v);

    if dims == [3 1]
        xi = [v; 0; 0; 0];

    else
        error('Unrecognized dimensions on v. Expected 3x1, instead found %dx%d', dims(1), dims(2));
    end

end