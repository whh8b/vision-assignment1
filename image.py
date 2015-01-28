#!/usr/bin/python

from __future__ import print_function
from operator import itemgetter

import numpy
import skimage
import skimage.io
import skimage.transform
import skimage.feature

class Util:
	@classmethod
	def discretize_angle(cls, angle):
		input_angle = angle
		if angle < 0:
			angle += 180
		closest = 180.0
		for c in [0.0, 45.0, 90.0, 135.0]:
			if numpy.abs(angle-c) < numpy.abs(angle-closest):
				closest = c
		Debug.Print("discretize_angle(%f): %f" % (input_angle, closest))
		return closest

	@classmethod
	def values_at(cls, array, y, x, z = 0):
		(array_height, array_width, array_depth) = array.shape
		return array[y % array_height, x % array_width, z]

class IntensityWeight:
	Red = 0.3
	Green = 0.6
	Blue = 0.1

class ChannelIndex:
	Red = 0
	Green = 1
	Blue = 2

class Derivative:
	WithRespectToY = 0
	WithRespectToX = 1

class Debug:
	@classmethod
	def Print(cls, string):
		print(string)
		pass

class Gauss:
	#
	# Calculate 1d Gaussian first derivative.
	#
	@classmethod
	def Gaussian1d1d(cls, i, sigma):
		return -1.0 * i * (1.0/(sigma*sigma)) * Gauss.Gaussian1d(i, sigma)
	
	#
	# Calculate 1d Gaussian
	#
	@classmethod
	def Gaussian1d(cls, i, sigma):
		exponent = -1.0 * ( (i*i) / (2.0*sigma*sigma))
		e_to_the = numpy.exp(exponent)
		inverse_term = 1.0 / (sigma * numpy.sqrt(numpy.pi * 2.0))
		result = inverse_term*e_to_the

		Debug.Print("i: " + str(i))
		Debug.Print("exponent: " + str(exponent))
		Debug.Print("e_to_the: " + str(e_to_the))
		Debug.Print("inverse_term: " + str(inverse_term))
		Debug.Print("result: " + str(result))

		return result

	#
	# Calculate 2d Gaussian
	#
	@classmethod
	def Gaussian2d(cls, i, j, sigma):
		exponent = -1.0 * ( (i*i + j*j) / (2.0*sigma*sigma))
		e_to_the = numpy.exp(exponent)
		inverse_term = 1.0 / (sigma * sigma * (numpy.pi * 2.0))
		result = inverse_term*e_to_the

		Debug.Print("i: " + str(i))
		Debug.Print("j: " + str(j))
		Debug.Print("exponent: " + str(exponent))
		Debug.Print("e_to_the: " + str(e_to_the))
		Debug.Print("inverse_term: " + str(inverse_term))
		Debug.Print("result: " + str(result))

		return result
		

class Image:

	@classmethod
	def ImageFromFile(cls, path):
		img = Image()
		img.image = skimage.img_as_float(skimage.io.imread(path))
		return img

	@classmethod
	def ImageFromArray(cls, array):
		img = Image()
		img.image = array
		return img

	def __init__(self):
		self.image = None
		self.gradient_image = None
		self.gradient_direction = None

	def store_gradient(self, path):
		if self.gradient_image != None:
			skimage.io.imsave(path, self.gradient_image)

	def store_image(self, path):
		if self.image != None:
			skimage.io.imsave(path, self.image)

	def canny(self, sigma, start_thresh, continue_thresh, save=None):
		#
		# First, change to grayscale
		#
		tmp = self._intensify(self.image)

		#
		# Compute the gradient.
		#
		g, gd = self._compute_gradient(tmp, sigma, save=save)

		#
		# Thin the gradient.
		#
		tmp = self._thin_gradient(g, gd)

		#
		# Relative the edges to the max
		#
		up = self._relative_up(tmp)

		#
		# Keep just the chained edges.
		#
		connected_edges = self._connected_edges(up, start_thresh, continue_thresh)

		return Image.ImageFromArray(connected_edges)

	def _up_rank(self, array):
		height, width = array.shape

		aa = numpy.zeros(height*width*1)
		aa = aa.reshape(height, width, 1)
		for x in range(width):
			for y in range(height):
				aa[y,x,0] = array[y,x]
		return aa

	def _down_rank(self, array):
		height, width, depth = array.shape

		aa = numpy.zeros(height*width)
		aa = aa.reshape(height, width)
		for x in range(width):
			for y in range(height):
				aa[y,x] = array[y,x]
		return aa


	def _relative_up(self, image):
		maxi = 0.0
		height, width, parts = image.shape
		up = numpy.zeros(height*width*parts)
		up = up.reshape(height, width, parts)
		for x in range(width):
			for y in range(height):
				for z in range(parts):
					if (image[y,x,z]>maxi): maxi = image[y,x,z]

		for x in range(width):
			for y in range(height):
				for z in range(parts):
					up[y,x,z] = image[y,x,z]/maxi
		return up

	def _save_separate_gradients(self, gradiants, path_base, extension="jpg"):
		height, width, depth = gradiants.shape

		assert depth == 2, "Depth must be 2 (ie, x and y derivatives)"

		x_deriv_base = numpy.zeros(height*width*1)
		x_deriv_base = x_deriv_base.reshape(height, width, 1)
		y_deriv_base = numpy.zeros(height*width*1)
		y_deriv_base = y_deriv_base.reshape(height, width, 1)
		for x in range(width):
			for y in range(height):
				x_deriv_base[y,x,0] = abs(gradiants[y,x,Derivative.WithRespectToX])
				y_deriv_base[y,x,0] = abs(gradiants[y,x,Derivative.WithRespectToY])
		x_deriv_base = self._relative_up(x_deriv_base)
		x_deriv_image = Image.ImageFromArray(x_deriv_base)
		x_deriv_image.store_image(path_base + "-x." + extension)

		y_deriv_base = self._relative_up(y_deriv_base)
		y_deriv_image = Image.ImageFromArray(y_deriv_base)
		y_deriv_image.store_image(path_base + "-y." + extension)

	def _connected_edges(self, edges, start_thresh, continue_thresh):
		#
		#
		#
		height, width, depth = edges.shape

		changes = []

		connected_edges = numpy.zeros(height*width*depth)
		connected_edges = connected_edges.reshape(height, width, depth)
		for x in range(width):
			for y in range(height):
				if edges[y,x] >= start_thresh:
					connected_edges[y,x,0] = edges[y,x]
					changes.append((y,x))

		while changes:
			updated_changes = []
			for (y,x) in changes:
				for i in (-1,0,1):
					for j in (-1,0,1):
						if i==0 and j==0: continue
						xx = x+i
						yy = y+j
						if xx >= 0 and xx < width and yy >= 0 and yy < height:
							Debug.Print("(%d,%d): %f vs %f (%f)" % 
								(yy, xx, edges[yy, xx], continue_thresh, connected_edges[yy,xx,0]))
							if connected_edges[yy,xx,0] == 0 and \
							   edges[yy,xx] > continue_thresh:
								Debug.Print("(%d,%d): added" % (yy,xx))
								connected_edges[yy,xx,0] = edges[yy,xx]
								updated_changes.append((yy,xx))
			changes = updated_changes
		return connected_edges

	def corners(self, sigma, threshold, neighborhood_size = 4):
		sortable = []
		intensity = self._intensify(self.image)
		gs, gd = self._compute_separate_gradient(intensity, sigma)
		gradient_height, gradient_width, gradient_parts = gs.shape

		corners_image = numpy.zeros(gradient_height*gradient_width*1)
		corners_image = corners_image.reshape(gradient_height, gradient_width, 1)

		corners_covariance = numpy.zeros(gradient_height*gradient_width)
		corners_covariance = corners_covariance.reshape(
			gradient_height,
			gradient_width)

		for x in range(gradient_width):
			for y in range(gradient_height):
				#
				# Compute the covarient matrix
				# in the neighborhood of (y,x)
				#
				covar = numpy.zeros(4)
				covar = covar.reshape(2,2)
				for i in range(-1*neighborhood_size, neighborhood_size+1):
					for j in range(-1*neighborhood_size, neighborhood_size+1):
						covar[0,0] += \
							Util.values_at(gs,y+j,x+i,Derivative.WithRespectToX)*\
							Util.values_at(gs,y+j,x+i,Derivative.WithRespectToX)
						covar[0,1] += \
							Util.values_at(gs,y+j,x+i,Derivative.WithRespectToX)*\
							Util.values_at(gs,y+j,x+i,Derivative.WithRespectToY)
						covar[1,0] += \
							Util.values_at(gs,y+j,x+i,Derivative.WithRespectToX)*\
							Util.values_at(gs,y+j,x+i,Derivative.WithRespectToY)
						covar[1,1] += \
							Util.values_at(gs,y+j,x+i,Derivative.WithRespectToY)*\
							Util.values_at(gs,y+j,x+i,Derivative.WithRespectToY)
				#
				# Compute the eigenvalues
				#
				w, v = numpy.linalg.eig(covar)
				Debug.Print("Eigenvalues at (%d, %d): %s" % (x,y,str(w)))

				#
				# Find the smaller of the two eigenvalues.
				#
				e = 0.0
				if w[0] <= w[1]:
					e = w[0]
				else:
					e = w[1]

				#
				# Compare to a threshold.
				#
				if e > threshold:
					# Add this point to a sortable list and
					# update the neighborhood where this threshold
					# value is bigger than existing values.
					sortable.append((e, y, x))
					for i in range(-1*neighborhood_size, neighborhood_size+1):
						for j in range(-1*neighborhood_size, neighborhood_size+1):
							# Using a slice index/assignment from numpy would be
							# awesome, but I don't know if we can.
							if (x+i) > 0 and (x+i) < gradient_width and \
							   (y+j) > 0 and (y+j) < gradient_height and\
								 corners_covariance[y+j,x+i] <= e:
								corners_covariance[y+j,x+i] = e

		#
		# Accentuate local maximums.
		#
		sortable = sorted(sortable, key=itemgetter(0), reverse=True)
		max_e = sortable[0][0]
		for e,y,x in sortable:
			Debug.Print("In neighborhood of (%d,%d):" % (y, x))
			for i in range(-1*neighborhood_size, neighborhood_size+1):
				for j in range(-1*neighborhood_size, neighborhood_size+1):
					if (x+i) > 0 and (x+i) < gradient_width and \
					   (y+j) > 0 and (y+j) < gradient_height and\
						 corners_covariance[y+j,x+i] < e:
						Debug.Print("Clearing %f at (%d,%d) <= %f" %
							(corners_covariance[y+j,x+i], y+j, x+i, e))
						corners_covariance[y+j,x+i] = 0.0
		#
		# Relativize corners
		#
		for x in range(gradient_width):
			for y in range(gradient_height):
				corners_image[y,x,0] = corners_covariance[y,x]/max_e

		return Image.ImageFromArray(corners_image)

	def native_canny(self, sigma):
		i = self._intensify(self.image)
		i = self._down_rank(i)
		e = skimage.filter.canny(i, sigma=sigma)
		e = self._up_rank(e)
		return Image.ImageFromArray(e)

	def native_corners(self, sigma, threshold):
		i = self._intensify(self.image)
		i = self._down_rank(i)
		e = skimage.feature.corner_harris(i, k=threshold, sigma=sigma)
		e = self._up_rank(e)
		return Image.ImageFromArray(e)

	def native_gaussian(self, sigma):
		return Image.ImageFromArray(skimage.filter.gaussian_filter(
			self.image,
			sigma,
			mode='wrap',
			multichannel=True))
	def intensify(self):
		return Image.ImageFromArray(self._intensify(self.image))

	def _intensify(self, image):
		(image_height, image_width, image_channels) = image.shape
		intensity = numpy.zeros(image_height*image_width*1)
		intensity = intensity.reshape(image_height, image_width, 1)

		# Apply the convolution to the image and its channels.
		for x in range(image_width):
			for y in range(image_height):
				intense = 0.0
				intensity[y,x,0]=image[y,x,ChannelIndex.Red]*IntensityWeight.Red+\
					image[y,x,ChannelIndex.Green]*IntensityWeight.Green + \
					image[y,x,ChannelIndex.Blue]*IntensityWeight.Blue
		#self.image = intensity
		return intensity

	def thin_gradient(self):
		img = Image.ImageFromArray(None)
		if self.gradient_image == None or self.gradient_direction == None:
			return img
		img.gradient_direction = self.gradient_direction
		img.gradient_image = self._thin_gradient(
			self.gradient_image,
			self.gradient_direction)
		return img

	def _thin_gradient(self, gradient_image, gradient_direction):
		(grad_height, grad_width, grad_channels) = gradient_image.shape
		thin_gradient = numpy.zeros(grad_height*grad_width*grad_channels)
		thin_gradient = thin_gradient.reshape(grad_height,
			grad_width,
			grad_channels)

		for x in range(grad_width):
			for y in range(grad_height):
				a = Util.discretize_angle(gradient_direction[y,x])
				if a == 0.0 or a == 180.0:
					#
					# Compare to right and left.
					#
					if Util.values_at(gradient_image,y,x,0) > \
						Util.values_at(gradient_image,y,x+1,0) and \
						Util.values_at(gradient_image,y,x,0) > \
						Util.values_at(gradient_image,y,x-1,0):
						thin_gradient[y,x,0] = gradient_image[y,x,0]
				elif a == 45.0:
					#
					# Compare to right, up and left, down
					#
					if Util.values_at(gradient_image,y,x,0) > \
						Util.values_at(gradient_image,y+1,x+1,0) and \
						Util.values_at(gradient_image,y,x,0) > \
						Util.values_at(gradient_image,y-1,x-1,0):
						thin_gradient[y,x,0] = gradient_image[y,x,0]
				elif a == 90.0:
					#
					# Compare to up and down
					#
					if Util.values_at(gradient_image,y,x,0) > \
						Util.values_at(gradient_image,y+1,x,0) and \
						Util.values_at(gradient_image,y,x,0) > \
						Util.values_at(gradient_image,y-1,x,0):
						thin_gradient[y,x,0] = gradient_image[y,x,0]
				elif a == 135.0:
					#
					# Compare to right, down and left, up
					#
					if Util.values_at(gradient_image,y,x,0) > \
						Util.values_at(gradient_image,y-1,x+1,0) and \
						Util.values_at(gradient_image,y,x,0) > \
						Util.values_at(gradient_image,y+1,x-1,0):
						thin_gradient[y,x,0] = gradient_image[y,x,0]
				else:
					assert False, "discretize_angle failed."
		#self.gradient_image = thin_gradient
		return thin_gradient

	def compute_gradient(self, sigma):
		img = Image.ImageFromArray(None)
		if self.gradient_image != None:
			img.gradient_image = self.gradient_image
			img.gradient_direction = self.gradient_direction
		else:
			img.gradient_image, img.gradient_direction = \
				self._compute_gradient(self.image,sigma)
		return img

	def compute_gaussian(self, sigma):
		return Image.ImageFromArray(self._compute_gaussian(self.image, sigma))

	def _compute_gaussian(self, image, sigma):
		height, width, depth = image.shape

		support = int(sigma*2 + 0.5)
		kernel = numpy.zeros((support*2+1)*(support*2+1))
		kernel = kernel.reshape((support*2+1), (support*2+1))
		kernel_sum = 0.0
		for i in range(-1*support, support+1):
			for j in range(-1*support, support+1):
				kernel[j+support, i+support] = Gauss.Gaussian2d(i, j, sigma)
				kernel_sum += kernel[j+support, i+support]

		gimage = numpy.zeros(height*width*depth)
		gimage = gimage.reshape(height, width, depth)
		for x in range(width):
			for y in range(height):
				for d in range(depth):
					convolve = 0.0
					for i in range(-1*support, support+1):
						for j in range(-1*support, support+1):
							convolve += (kernel[j+support, i+support] * 
								Util.values_at(image, i+y, j+x, d))
					Debug.Print("(%d, %d, %d): %f to %f" % (y,x,d,image[y,x,d], convolve))
					gimage[y,x,d] = convolve
		return gimage

	def _compute_gradient(self, image, sigma, save=None):
		separate_gradient, gradient_direction = \
			self._compute_separate_gradient(image, sigma)
		gradient_height, gradient_width, gradient_parts = separate_gradient.shape

		if save != None:
			self._save_separate_gradients(separate_gradient, save)

		gradient_image = numpy.zeros(gradient_height * gradient_width * 1)
		gradient_image = gradient_image.reshape(gradient_height, gradient_width, 1)
		for x in range(gradient_width):
			for y in range(gradient_height):
				y_grad = separate_gradient[y,x,Derivative.WithRespectToY]
				x_grad = separate_gradient[y,x,Derivative.WithRespectToX]
				gradient_image[y,x,0] = numpy.sqrt(x_grad*x_grad + y_grad*y_grad)
		return (gradient_image, gradient_direction)

	def _compute_separate_gradient(self, image, sigma):

		(image_height, image_width, image_channels) = image.shape

		#
		# We only allow this on images that are already intensified.
		#
		assert image_channels == 1, "One channel images only."

		separate_gradient = numpy.zeros(image_height*image_width * 2)
		separate_gradient = separate_gradient.reshape(image_height, image_width, 2)

		(image_height, image_width, image_channels) = image.shape
		gradient_direction = numpy.zeros(image_height*image_width)
		gradient_direction = gradient_direction.reshape(image_height, image_width)

		convolution_range = int(sigma*2 + 0.5)

		# calculate factor as the gaussian kernel of the
		# convolution
		factor = numpy.zeros(convolution_range*2+1)
		d_factor = numpy.zeros(convolution_range*2+1)
		for c in range(-1*convolution_range, convolution_range+1):
			# use the 2d gaussian to calculate the
			# amount this pixel should contribute overall.
			factor[c + convolution_range] = Gauss.Gaussian1d(c, sigma)
			d_factor[c + convolution_range] = Gauss.Gaussian1d1d(c, sigma)

		for x in range(image_width):
			for y in range(image_height):
				x_grad = 0.0
				y_grad = 0.0
				# we are calculating the out(x,y)
				# at this point.
				Debug.Print("(y,x,0): (" + str(y) + "," + str(x) + ",0): "
					+ str(image[y,x,0]))

				for i in range(-1*convolution_range, convolution_range+1):
					for j in range(-1*convolution_range, convolution_range+1):
						# use the 2d gaussian to calculate the
						# amount this pixel should contribute overall.
						x_grad += Util.values_at(image, y+j, x+i, 0)* \
							d_factor[i+convolution_range]* \
							factor[j + convolution_range]

						y_grad += Util.values_at(image, y+j, x+i, 0)* \
							factor[i + convolution_range]* \
							d_factor[j + convolution_range]

				#separate_gradient[y,x,0] = numpy.sqrt(x_grad*x_grad + y_grad*y_grad)
				separate_gradient[y,x,Derivative.WithRespectToY] = y_grad
				separate_gradient[y,x,Derivative.WithRespectToX] = x_grad

				if x_grad == 0.0:
					gradient_direction[y,x] = numpy.rad2deg(numpy.pi/2.0)
				else:
					gradient_direction[y,x] = numpy.rad2deg(numpy.arctan(y_grad/x_grad))
				Debug.Print("gradient image (y,x,0): ("
					+ str(y)
					+ ","
					+ str(x)
					+ ",0): "
					+ str(separate_gradient[y,x,0]))
				Debug.Print("gradient direction (y,x,0): ("
					+ str(y)
					+ ","
					+ str(x)
					+ "): "
					+ str(gradient_direction[y,x])
					+ " -> "
					+ str(Util.discretize_angle(gradient_direction[y,x])))
		return (separate_gradient, gradient_direction)

if __name__ == "__main__":
	print("Loading image.")
#	image = Image("./line.jpg")
#	image = Image.ImageFromFile("./circle.jpg")
#	image = Image.ImageFromFile("./building.jpg")
#	image = Image.ImageFromFile("./building-crop.jpg")
#	image = Image.ImageFromFile("./checker.jpg")
	image = Image.ImageFromFile("./checkers-crop.jpg")
#	image = Image.ImageFromFile("./corner.jpg")

#	image = image.corners(2.0, 0.1)
#	image = image.native_corners(1.0, 0.1)
#	me = image.compute_gaussian(2.0)
#	me.store_image("./me-gauss.jpg")
#	them = image.native_gaussian(2.0)
#	them.store_image("./them-gauss.jpg")

	edges = image.canny(2.0, 0.4, 0.1, save="./me-grad")
	edges.store_image("./me-edges.jpg")
	#edges = image.native_canny(2.0)
	#edges.store_image("./them-edges.jpg")
