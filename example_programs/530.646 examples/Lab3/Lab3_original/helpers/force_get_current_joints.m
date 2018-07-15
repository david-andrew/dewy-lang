function [ q ] = force_get_current_joints(ur5)
%Get the current joints of the ur5 ensuring that it returns real values
%   if the ur5.get_current_joints is called too quickly, it may not return
%   the actual value of the joints. This function will call
%   get_current_joints until it gets an actual response
%   
%   input: ur5 is the ur5_interface object
%   output: q is a 6x1 vector of the current joints of the ur5.
%       q has an offset so that ur5.home is the zero angle configuration



    %call get_current_joints until the values are slightly different from
    %due to numerical imprecision
    while true
        q = ur5.get_current_joints - ur5.home;
        if norm(q + ur5.home) > 2*eps(norm(q))
            break
        end
    end


end

