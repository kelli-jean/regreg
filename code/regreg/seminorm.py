import numpy as np

import regression; reload(regression)
from regression import FISTA, ISTA
from problems import linmodel

class problem(object):

    """
    A problem class with a smooth component, and a seminorm component stored in self.semi
    """

    def __init__(self, data, semi):
        self.semi = semi
        self.initialize(data)

    @property
    def output(self):
        r = self.Y - np.dot(self.X, self.coefs)
        return self.coefs.copy(), r
    
    def set_coefs(self, coefs):
        self._coefs = coefs

    def get_coefs(self):
        return self._coefs
    coefs = property(get_coefs, set_coefs)

    def set_response(self,Y):
        self._Y = Y

    def get_response(self):
        return self._Y
    Y = property(get_response, set_response)

    @property
    def default_coefs(self):
        return np.zeros(self.p)

    def obj(self, beta):
        return self.obj_smooth(beta) + self.obj_rough(beta)

    def obj_rough(self, beta):
        return self.semi.evaluate(beta)

    def proximal(self, coefs, grad, L):
        return self.semi.proximal(coefs, grad, L)

class squaredloss(problem):

    """
    A class for combining squared error loss with a general seminorm
    """


    def __init__(self, X, Y):
        """
        Generate initial tuple of arguments for update.
        """

        self.X = X
        self.Y = Y
        self.n, self.p = self.X.shape

    def obj_smooth(self, beta):
        #Smooth part of objective
        return ((self.Y - np.dot(self.X, beta))**2).sum() / 2. 

    def grad(self, beta):
        XtXbeta = np.dot(self.X.T, np.dot(self.X, beta)) 
        return XtXbeta - np.dot(self.Y,self.X) 

    def add_seminorm(self, seminorm, initial=None, smooth_multiplier=1):
        return seminorm.problem(self.obj_smooth, self.grad, smooth_multiplier=smooth_multiplier,
                                initial=initial)
  
class dummy_problem(object):
    """
    A generic way to specify a problem
    """
    def __init__(self, smooth, grad_smooth, nonsmooth, prox, initial, smooth_multiplier=1):
        self.coefs = initial * 1.
        self.obj_smooth = smooth
        self.nonsmooth = nonsmooth
        self._grad = grad_smooth
        self._prox = prox
        self.smooth_multiplier = smooth_multiplier

    def obj(self, x):
        return self.smooth_multiplier * self.obj_smooth(x) + self.nonsmooth(x)

    def grad(self, x):
        return self.smooth_multiplier * self._grad(x)

    def proximal(self, x, g, L):
        z = x - g / L
        return self._prox(z, L)

class seminorm_atom(object):

    """
    A seminorm atom class
    """

    #XXX spec as 1d array could mean weights?
    #XXX matrix multiply should be sparse if possible
    def __init__(self, spec, l=1.):
        if type(spec) == type(1):
            self.p = self.m = spec
            self.D = None
        else:
            D = spec
            if D.ndim == 1:
                D = D.reshape((1,-1))
            self.D = D
            self.m, self.p = D.shape
        self.l = l
        
    def evaluate(self, x):
        """
        Abstract method. Evaluate the norm of x.
        """
        raise NotImplementedError

    def primal_prox(self, x, L):
        """
        Return (unique) minimizer

        .. math::

           v^{\lambda}(x) = \text{argmin}_{v \in \real^p} \frac{L}{2}
           \|x-v\|^2_2 + \lambda h(Dv)

        where *p*=x.shape[0] and :math:`h(v)`=self.evaluate(v).
        """
        raise NotImplementedError

    def dual_prox(self, u, L):
        """
        Return a minimizer

        .. math::

           v^{\lambda}(u) \in \text{argmin}_{v \in \real^m} \frac{L}{2}
           \|u-D'v\|^2_2  s.t.  h^*(v) \leq \lambda

        where *m*=u.shape[0] and :math:`h^*` is the 
        conjugate of self.evaluate.
        """
        raise NotImplementedError

    def multiply_by_DT(self, u):
        if self.D is not None:
            return np.dot(u, self.D)
        else:
            return u

    def multiply_by_D(self, x):
        if self.D is not None:
            return np.dot(self.D, x)
        else:
            return x

    def problem(self, smooth, grad_smooth, smooth_multiplier=1., initial=None):
        """
        Return a problem instance 
        """
        prox = self.primal_prox
        nonsmooth = self.evaluate
        if initial is None:
            initial = np.random.standard_normal(self.p)
        return dummy_problem(smooth, grad_smooth, nonsmooth, prox, initial, smooth_multiplier)


class l1norm(seminorm_atom):

    """
    The l1 norm
    """

    def evaluate(self, x):
        """
        The L1 norm of Dx.
        """
        if self.D is None:
            return self.l * np.fabs(x).sum()
        else:
            return self.l * np.fabs(np.dot(self.D, x)).sum()

    def evaluate_dual(self, u):
        inbox = np.product(np.less_equal(np.fabs(u), self.l))
        if inbox:
            return 0
        else:
            return np.inf

    def primal_prox(self, x,  L=1):
        """
        Return (unique) minimizer

        .. math::

            v^{\lambda}(x) = \text{argmin}_{v \in \real^p} \frac{L}{2}
            \|x-v\|^2_2 + \lambda \|Dv\|_1

        where *p*=x.shape[0], :math:`\lambda`=self.l. 
        If :math:`D=I` this is just soft thresholding

        .. math::

            v^{\lambda}(x) = \text{sign}(x) \max(|x|-\lambda/L, 0)
        """

        if self.D is None:
            return np.sign(x) * np.maximum(np.fabs(x)-self.l/L, 0)
        else:
            return FISTAsoln # will barf

    def dual_prox(self, u, L=1):
        """
        Return a minimizer

        .. math::

            v^{\lambda}(u) \in \text{argmin}_{v \in \real^m} \frac{L}{2}
            \|u-D'v\|^2_2 s.t. \|v\|_{\infty} \leq \lambda

        where *m*=u.shape[0], :math:`\lambda`=self.l. 
        This is just truncation: np.clip(u, -self.l/L, self.l/L).
        """
        return np.clip(u, -self.l, self.l)

class l2norm(seminorm_atom):

    """
    The l2 norm
    """
    tol = 1.0e-10
    
    def evaluate(self, x):
        """
        The L2 norm of Dx.
        """
        if self.D is not None:
            return self.l * np.linalg.norm(np.dot(self.D, x))
        else:
            return self.l * np.linalg.norm(x)

    def evaluate_dual(self, u):
        inball = (np.linalg.norm(u) <= self.l)
        if inball:
            return 0
        else:
            return np.inf

    def primal_prox(self, x,  L=1):
        """
        Return (unique) minimizer

        .. math::

            v^{\lambda}(x) = \text{argmin}_{v \in \real^p} \frac{L}{2}
            \|x-v\|^2_2 + \lambda \|Dv\|_2

        where *p*=x.shape[0], :math:`\lambda`=self.l. 
        If :math:`D=I` this is just a "James-Stein" estimator

        .. math::

            v^{\lambda}(x) = \max(1 - \frac{\lambda}{\|x\|_2}, 0) x
        """

        if self.D is None:
            n = np.linalg.norm(x)
            if n >= self.l / L:
                return np.zeros(x.shape)
            else:
                return (1 - self.l / (L*n) * (1 - l2norm.tol)) * x
        else:
            return FISTAsoln # this will barf

    def dual_prox(self, u,  L=1):
        """
        Return a minimizer

        .. math::

            v^{\lambda}(u) \in \text{argmin}_{v \in \real^m} \frac{L}{2}
            \|u-D'v\|^2_2 + \lambda \|v\|_2

        where *m*=u.shape[0], :math:`\lambda`=self.l. 
        This is just truncation

        .. math::

            v^{\lambda}(u) = \min(1, \frac{\lambda/L}{\|u\|_2}) u
        """
        n = np.linalg.norm(u)
        if n < self.l:
            return u
        else:
            return (self.l * (1 - l2norm.tol)/ n) * u

class seminorm(object):
    """
    A seminorm container class for storing/combining seminorm_atom classes
    """
    def __init__(self, *atoms):
        self.atoms = []
        self.primal_dim = -1
        self.segments = []
        idx = 0
        for atom in atoms:
            if self.primal_dim < 0:
                self.primal_dim = atom.p
            else:
                if atom.p != self.primal_dim:
                    raise ValueError("primal dimensions don't agree")
            self.atoms.append(atom)
            self.segments.append(slice(idx, idx+atom.m))
            idx += atom.m
        self.total_dual = idx

    def __add__(self,y):
        #Combine two seminorms
        def atoms():
            for obj in [self, y]:
                for atom in obj.atoms:
                    yield atom
        return seminorm(*atoms())

    def evaluate(self, x):
        out = 0.
        for atom in self.atoms:
            out += atom.evaluate(x)
        return out
    
    def evaluate_dual(self, u):
        out = 0.
        for atom, segment in zip(self.atoms, self.segments):
            out += atom.evaluate_dual(u[segment])
        return out
    
    def dual_prox(self, u, L_D=1.):
        """
        Return (unique) minimizer

        .. math::

           v^{\lambda}(u) = \text{argmin}_{v \in \real^m} \frac{1}{2}
           \|v-u\|^2_2  s.t.  h^*_i(v) \leq \infty, 0 \leq i \leq M-1

        where *m*=u.shape[0]=np.sum(self.dual_dims), :math:`M`=self.M
        and :math:`h^*_i` is the conjugate of 
        self.atoms[i].l * self.atoms[i].evaluate and 
        :math:`\lambda_i`=self.atoms[i].l.

        This is used in the inner loop with :math:`u=z-g/L` when finding
        self.primal_prox, i.e., the signal approximator problem.
        """
        v = np.empty(u.shape)
        for atom, segment in zip(self.atoms, self.segments):
            v[segment] = atom.dual_prox(u[segment], L_D)
        return v

    default_solver = ISTA
    def primal_prox(self, y, L_P=1, with_history=False, debug=False):
        #XXX make dualp persistent...
        dualp = self.dual_problem(y, L_P=L_P)
        solver = seminorm.default_solver(dualp)
        solver.debug = debug
        history = solver.fit(max_its=2000)
        print history.shape, L_P, np.max(history), np.min(history), 'niterations'
        if with_history:
            return self.primal_from_dual(y, solver.problem.coefs), history
        else:
            return self.primal_from_dual(y, solver.problem.coefs)

    def primal_from_dual(self, y, u):
        """

        """
        x = y * 1.
        for atom, segment in zip(self.atoms, self.segments):
            x -= atom.multiply_by_DT(u[segment])
        return x

    def dual_problem(self, y, L_P=1, initial=None):
        """
        Return a problem instance of the dual
        prox problem with a given y value.
        """
        
        def smooth(v):
            primal = self.primal_from_dual(y, v)
            return (primal**2).sum() / 2.
        def grad_smooth(v):
            primal = self.primal_from_dual(y, v)
            g = np.zeros(self.total_dual)
            for atom, segment in zip(self.atoms, self.segments):
                g[segment] = -atom.multiply_by_D(primal)
            return g
        if initial is None:
            z = np.random.standard_normal(self.total_dual)
            initial = self.dual_prox(z, 1./L_P)
        nonsmooth = self.evaluate_dual
        prox = self.dual_prox
        return dummy_problem(smooth, grad_smooth, nonsmooth, prox, initial, 1./L_P)

    def problem(self, smooth, grad_smooth, smooth_multiplier=1., initial=None):
        prox = self.primal_prox
        nonsmooth = self.evaluate
        if initial is None:
            initial = self.dual_prox(np.random.standard_normal(self.primal_dim))
        return dummy_problem(smooth, grad_smooth, nonsmooth, prox, initial, smooth_multiplier)
        
import pylab

def fused_example():

    x=np.random.standard_normal(500); x[100:150] += 7

    sparsity = l1norm(500, l=1.3)
    D = (np.identity(500) + np.diag([-1]*499,k=1))[:-1]
    fused = l1norm(D, l=1.5)

    pen = seminorm(sparsity,fused)
    soln, vals = pen.primal_prox(x, 1)
    
    # solution

    pylab.figure(num=1)
    pylab.clf()
    pylab.plot(soln, c='g')
    pylab.scatter(np.arange(x.shape[0]), x)

    # objective values

    pylab.figure(num=2)
    pylab.clf()
    pylab.plot(vals)

def lasso_example():

    sparsity = l1norm(500, l=20.)
    X = np.random.standard_normal((1000,500))
    Y = np.random.standard_normal((1000,))
    regloss = squaredloss(X,Y)
    p=regloss.add_seminorm(sparsity)
    solver=ISTA(p)
    solver.debug = True
    vals = solver.fit(max_its=2000)
    soln = solver.problem.coefs

    # solution

    pylab.figure(num=1)
    pylab.clf()
    pylab.plot(soln, c='g')

    # objective values

    pylab.figure(num=2)
    pylab.clf()
    pylab.plot(vals)

def group_lasso_example():

    def selector(p, slice):
        return np.identity(p)[slice]
    penalties = [l2norm(selector(500, slice(i*100,(i+1)*100)), l=100.) for i in range(5)]
    group_lasso = seminorm(*penalties)
    x = np.random.standard_normal(500)
    group_lasso.primal_prox(x, 1.)
    X = np.random.standard_normal((1000,500))
    Y = np.random.standard_normal((1000,))
    regloss = squaredloss(X,Y)
    p=regloss.add_seminorm(group_lasso, smooth_multiplier=1.0e-03)
    solver=ISTA(p)
    solver.debug = True
    vals = solver.fit(max_its=2000, start_inv_step=1000.)
    soln = solver.problem.coefs

    # solution

    pylab.figure(num=1)
    pylab.clf()
    pylab.plot(soln, c='g')

    # objective values

    pylab.figure(num=2)
    pylab.clf()
    pylab.plot(vals)
